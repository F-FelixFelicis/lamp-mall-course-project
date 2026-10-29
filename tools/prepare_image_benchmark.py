"""Freeze the existing photo sources and make blind, human annotation files."""
from collections import defaultdict
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/image_search_benchmark'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def dhash(path):
    with Image.open(path) as image:
        pixels=list(image.convert('L').resize((9,8)).getdata())
    bits=0
    for y in range(8):
        for x in range(8):bits=(bits<<1)|int(pixels[y*9+x]>pixels[y*9+x+1])
    return bits


def prepare(refresh_unannotated=False):
    catalog=json.loads((ROOT/'assets/catalog/catalog.json').read_text(encoding='utf-8'))
    queries=json.loads((ROOT/'assets/image_search_queries/manifest.json').read_text(encoding='utf-8'))
    gallery=[]
    for row in sorted(catalog['products'],key=lambda r:r['sku_code']):
        path=ROOT/'assets/catalog'/row['photo']['file']
        gallery.append({'sku_code':row['sku_code'],'name':row['name'],'category':row['category'],
            'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'source_page':row['photo']['page'],
            'author':row['photo']['author'],'license_url':row['photo']['license'],
            'source_note':row['photo'].get('source_note','')})
    counts=defaultdict(int);query_rows=[]
    for row in queries['images']:
        path=ROOT/'assets/image_search_queries'/row['file']
        if digest(path)!=row['sha256']:raise ValueError('Query manifest hash mismatch')
        split='dev' if counts[row['preliminary_category']]==0 else 'test'
        counts[row['preliminary_category']]+=1
        query_rows.append({'id':row['id'],'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),
            'preliminary_category':row['preliminary_category'],'split':split,'source_page':row['source_page'],
            'author':row['photographer'],'license_url':row['license_url']})
    if {g['sha256'] for g in gallery}&{q['sha256'] for q in query_rows}:
        raise ValueError('Identical query/gallery files found')
    def photo_id(url):
        match=re.search(r'(\d+)/?$',url)
        return 'pexels:'+match[1] if 'pexels.com/' in url and match else url.rstrip('/')
    if {photo_id(g['source_page']) for g in gallery}&{photo_id(q['source_page']) for q in query_rows}:
        raise ValueError('Same-source query/gallery photos found')
    hashes={r['path']:dhash(ROOT/r['path']) for r in gallery+query_rows}
    near=[{'query_id':q['id'],'sku_code':g['sku_code'],'dhash_distance':(hashes[q['path']]^hashes[g['path']]).bit_count()}
        for q in query_rows for g in gallery if (hashes[q['path']]^hashes[g['path']]).bit_count()<=4]
    dataset={'schema_version':1,'split_rule':'first collected query per preliminary category -> dev; remaining -> test',
        'seed':20261029,'gallery':gallery,'queries':query_rows,'near_duplicate_candidates':near,
        'relevance_rule':'2=strong visual similarity; 1=weak similarity; 0=not relevant. Category alone is insufficient.'}
    dataset['data_version']=sha256(json.dumps(dataset,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'dataset.json'
    if target.exists() and json.loads(target.read_text(encoding='utf-8'))!=dataset:
        if not refresh_unannotated:
            raise ValueError('Frozen dataset changed; create a new version or explicitly refresh an unannotated draft')
        for path in OUT.glob('*review*.json'):
            document=json.loads(path.read_text(encoding='utf-8'))
            if document.get('reviewer') or any(any(v is not None for v in q['ratings'].values()) for q in document['queries']):
                raise ValueError('Human annotations already exist; cannot refresh this dataset')
        for path in OUT.glob('*template.json'):
            document=json.loads(path.read_text(encoding='utf-8'))
            if document.get('reviewer') or any(any(v is not None for v in q['ratings'].values()) for q in document['queries']):
                raise ValueError('Nonblank annotation template; cannot refresh')
        history=ROOT/'.qa/m4-benchmark/dataset-history';history.mkdir(parents=True,exist_ok=True)
        old=json.loads(target.read_text(encoding='utf-8'))
        (history/(old['data_version']+'.json')).write_bytes(target.read_bytes())
    target.write_text(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    template={'schema_version':1,'data_version':dataset['data_version'],'reviewer':'',
        'queries':[{'query_id':q['id'],'duplicate_checked':False,'exclude_reason':'','decision_reason':'',
            'ratings':{g['sku_code']:None for g in gallery}} for q in query_rows]}
    for name in ['review-a.template.json','review-b.template.json','adjudication.template.json']:
        path=OUT/name
        if not path.exists() or refresh_unannotated:path.write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    html=(ROOT/'tools/templates/image_annotation.html').read_text(encoding='utf-8')
    (OUT/'annotation.html').write_text(html.replace('__DATASET_JSON__',json.dumps(dataset,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    print(f'Frozen {len(gallery)} gallery / {len(query_rows)} query images; dev=5, test=10; near-duplicate candidates={len(near)}')
    print('Human annotations remain blank:',target)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-unannotated',action='store_true',help='Archive and refresh a draft only while all annotation templates are blank')
    prepare(parser.parse_args().refresh_unannotated)
