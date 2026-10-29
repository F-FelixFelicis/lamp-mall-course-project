from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance
import pytest
from sqlalchemy import select

from app.commerce_models import MerchantOffer, MerchantProfile, Product, ProductImage, ProductSku
from app.image_features import COLOR_VERSION, ImageInputError, ResnetEncoder, color_vector, decode_image
from app.image_models import ImageSearchLog
from test_m1 import client
from test_m2 import actors, approved_product, live_offer, on_sale, ok, upload


class FastEncoder:
    """Only the model boundary is replaced; ranking, files, DB and API stay real."""
    weights_sha256 = 'test-model-sha'
    runtime = {"device":"test-only"}
    def encode(self,image):
        return np.tile(color_vector(image),4)/2


@pytest.fixture
def indexed(client,actors):
    p=approved_product(client,actors)
    offer=live_offer(client,actors,p['skus'][0]['id'])
    on_sale(client,actors,p)
    engine=client.app.state.image_index
    engine._encoder=FastEncoder()
    result=ok(client.post('/api/v1/admin/image-search/index',headers=actors['admin']))
    assert result['ready'] and not result['needs_rebuild']
    return p,offer,result


def image_bytes(color='gold'):
    stream=BytesIO();Image.new('RGB',(64,64),color).save(stream,'PNG');return stream.getvalue()


def search(client,method='color',**options):
    return client.post('/api/v1/search/image',data={'method':method,**options},
        files={'file':('query.png',image_bytes(),'image/png')})


def test_real_histogram_and_content_validation():
    a=decode_image(image_bytes('red'));b=decode_image(image_bytes('blue'))
    assert np.isclose(np.dot(color_vector(a),color_vector(a)),1)
    assert np.dot(color_vector(a),color_vector(b)) < .1
    for bad in [b'not an image',b'<svg></svg>']:
        with pytest.raises(ImageInputError):decode_image(bad)
    tiny=BytesIO();Image.new('RGB',(10,10)).save(tiny,'PNG')
    with pytest.raises(ImageInputError):decode_image(tiny.getvalue())


def test_admin_index_permissions_and_unavailable(client,actors):
    assert client.get('/api/v1/admin/image-search/status').status_code==401
    assert client.post('/api/v1/admin/image-search/index',headers=actors['buyer']).status_code==403
    status=ok(client.get('/api/v1/admin/image-search/status',headers=actors['admin']))
    assert status['ready'] is False and status['query_images_retained'] is False
    unavailable=search(client)
    assert unavailable.status_code==503 and unavailable.json()['code']=='IMAGE_SEARCH_UNAVAILABLE'
    assert client.get('/api/v1/products').status_code==200


def test_rank_privacy_logging_and_baseline(client,actors,indexed):
    before=set(client.app.state.settings.upload_dir.iterdir())
    for method in ['deep','color']:
        result=ok(search(client,method,k=5))
        assert len(result['items'])==1
        row=result['items'][0]
        assert row['sku_id']==indexed[0]['skus'][0]['id'] and row['lowest_price']==199
        assert row['score']==pytest.approx(1)
        assert client.get(row['matched_image_url']).status_code==200
    assert set(client.app.state.settings.upload_dir.iterdir())==before
    assert client.get('/api/v1/admin/image-search/logs',headers=actors['buyer']).status_code==403
    logs=ok(client.get('/api/v1/admin/image-search/logs',headers=actors['admin']))
    assert len(logs)==2
    assert not ({'filename','raw','embedding','query_sha256','image_url'} & set(logs[0]))
    with client.app.state.session_factory() as s:
        assert len(s.scalars(select(ImageSearchLog)).all())==2


@pytest.mark.parametrize('state',['stock','off_sale','sku','association','merchant','expiry'])
def test_stale_index_never_bypasses_current_business_state(client,actors,indexed,state):
    p,o,_=indexed
    from datetime import datetime,timedelta
    with client.app.state.session_factory.begin() as s:
        if state=='stock':s.get(MerchantOffer,o['id']).stock_qty=0
        if state=='off_sale':s.get(Product,p['id']).status='OFF_SALE'
        if state=='sku':s.get(ProductSku,p['skus'][0]['id']).status='INACTIVE'
        if state=='association':s.delete(s.scalar(select(ProductImage).where(ProductImage.sku_id==p['skus'][0]['id'])))
        if state=='merchant':s.get(MerchantProfile,1).certification_status='REJECTED'
        if state=='expiry':s.get(MerchantOffer,o['id']).expired_at=datetime.now()-timedelta(days=1)
    assert ok(search(client))['items']==[]
    status=ok(client.get('/api/v1/admin/image-search/status',headers=actors['admin']))
    assert status['needs_rebuild']


def test_live_price_category_filter_and_sku_dedup(client,actors,indexed):
    p,o,_=indexed
    new=upload(client,actors['seller'])
    with client.app.state.session_factory.begin() as s:
        s.add(ProductImage(product_id=p['id'],sku_id=p['skus'][0]['id'],file_id=new['id']))
        s.get(MerchantOffer,o['id']).price=155
    ok(client.post('/api/v1/admin/image-search/index',headers=actors['admin']))
    result=ok(search(client))
    assert len(result['items'])==1 and result['items'][0]['lowest_price']==155
    assert ok(search(client,category_id=1))['items']==[]
    assert search(client,k=21).status_code==422
    assert search(client,method='arbitrary').status_code==422


def test_invalid_uploads_do_not_log_or_persist(client,actors,indexed):
    for data,status in [(b'fake image',422),(b'x'*(5*1024*1024+1),413)]:
        response=client.post('/api/v1/search/image',files={'file':('fake.png',data,'image/png')})
        assert response.status_code==status
    with client.app.state.session_factory() as s:
        assert not s.scalars(select(ImageSearchLog)).all()


def test_failed_rebuild_preserves_previous_index(client,actors,indexed):
    engine=client.app.state.image_index
    original=sha256(engine.path.read_bytes()).hexdigest()
    with client.app.state.session_factory.begin() as s:
        row=s.get(ProductImage,1)
        from app.commerce_models import UploadedFile
        s.get(UploadedFile,row.file_id).sha256='0'*64
    response=client.post('/api/v1/admin/image-search/index',headers=actors['admin'])
    assert response.status_code==503
    assert sha256(engine.path.read_bytes()).hexdigest()==original
    assert ok(search(client))['items']==[]


def test_corrupt_index_and_missing_model_fail_closed(client,actors,indexed):
    engine=client.app.state.image_index
    engine.path.write_bytes(b'not npz')
    assert search(client).status_code==503
    assert client.get('/api/v1/products').status_code==200
    with pytest.raises(Exception,match='权重'):
        ResnetEncoder(Path('this-checkpoint-does-not-exist.pth'))


def test_missing_image_file_is_not_returned(client,actors,indexed):
    engine=client.app.state.image_index
    meta,_,_=engine.load()
    (client.app.state.settings.upload_dir/meta['rows'][0]['storage_key']).unlink()
    assert ok(search(client))['items']==[]


def test_large_valid_query_stays_in_memory_and_oversize_body_is_bounded(client,actors,indexed,monkeypatch):
    import starlette.formparsers as parser
    from app.image_query_memory import MAX_QUERY_BODY
    opened=[];original=parser.SpooledTemporaryFile
    def tracked(*args,**kwargs):
        f=original(*args,**kwargs);opened.append(f);return f
    monkeypatch.setattr(parser,'SpooledTemporaryFile',tracked)
    random=np.random.default_rng(9).integers(0,256,(800,800,3),dtype=np.uint8)
    output=BytesIO();Image.fromarray(random).save(output,'PNG');raw=output.getvalue()
    assert len(raw)>1024*1024
    response=client.post('/api/v1/search/image',data={'method':'color'},files={'file':('query.png',raw,'image/png')})
    assert response.status_code==200,response.text
    assert opened and all(not f._rolled and f.closed for f in opened), [(f._rolled,f.closed) for f in opened]
    response=client.post('/api/v1/search/image',content=iter([b'x'*1024*1024 for _ in range(MAX_QUERY_BODY//(1024*1024)+1)]),headers={'Content-Type':'multipart/form-data; boundary=oversized'})
    assert response.status_code==413 and response.json()['code']=='FILE_TOO_LARGE'


def test_startup_preloads_model_and_missing_model_does_not_block_catalog(client,actors,indexed,monkeypatch):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.image_features import SearchUnavailable
    app=create_app(replace(client.app.state.settings,app_env='local'))
    engine=app.state.image_index
    calls=[]
    monkeypatch.setattr(engine,'encoder',lambda:calls.append('loaded'))
    # A tiny local sentinel tests lifecycle control; it is never passed to Torch.
    engine.weights_path=engine.folder/'test-preload-sentinel'
    engine.weights_path.write_bytes(b'test')
    with TestClient(app) as local:
        assert local.get('/api/v1/products').status_code==200
    assert calls==['loaded']
    def unavailable():raise SearchUnavailable('missing test model')
    monkeypatch.setattr(engine,'encoder',unavailable)
    with TestClient(app) as local:
        assert local.get('/api/v1/products').status_code==200


def test_real_resnet_embedding_is_repeatable_and_brightness_robust():
    from app.config import API_ROOT
    weights=API_ROOT/'.local/models/resnet18-f37072fd.pth'
    if not weights.is_file():pytest.skip('Official local checkpoint not prepared')
    model=ResnetEncoder(weights)
    image=decode_image((API_ROOT.parents[1]/'assets/catalog/pexels-1112598.jpg').read_bytes())
    a=model.encode(image);b=model.encode(ImageEnhance.Brightness(image).enhance(.9))
    assert a.shape==(512,) and np.isclose(np.linalg.norm(a),1)
    assert np.dot(a,b)>.9
    assert np.allclose(a,model.encode(image),atol=1e-6)
