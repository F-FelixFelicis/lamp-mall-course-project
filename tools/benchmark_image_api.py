"""Measure real HTTP-handler time on the isolated 20-photo QA catalogue."""
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'apps/api'))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def main():
    folder=ROOT/'.qa/m4-browser';db=folder/'browser.db'
    if not db.is_file():raise SystemExit('Prepare the isolated browser QA catalogue first')
    settings=Settings('test',f'sqlite:///{db.as_posix()}','m4-local-browser-acceptance-secret-29',60,'123456',folder/'uploads')
    app=create_app(settings)
    dataset=json.loads((ROOT/'assets/image_search_benchmark/dataset.json').read_text(encoding='utf-8'))
    queries=[q for q in dataset['queries'] if q['split']=='test']
    rows=[]
    with TestClient(app) as client:
        for method in ['deep','color']:
            for iteration,q in enumerate([queries[0]]+queries):
                raw=(ROOT/q['path']).read_bytes();tick=time.perf_counter()
                response=client.post('/api/v1/search/image',data={'method':method,'k':'5'},files={'file':('reference.jpg',raw,'image/jpeg')})
                elapsed=(time.perf_counter()-tick)*1000
                if response.status_code!=200:raise RuntimeError(response.text)
                body=response.json();rows.append({'method':method,'phase':'cold' if iteration==0 else 'warm',
                    'query_id':q['id'],'request_id':body['query_id'],'index_version':body['index_version'],
                    'roundtrip_ms':round(elapsed,3),'handler_ms':body['elapsed_ms'],'results':len(body['items'])})
    summary={}
    for method in ['deep','color']:
        warm=[r['roundtrip_ms'] for r in rows if r['method']==method and r['phase']=='warm']
        cold=next(r['roundtrip_ms'] for r in rows if r['method']==method and r['phase']=='cold')
        summary[method]={'first_request_ms':cold,'warm_p95_ms':round(float(np.percentile(warm,95)),3),'warm_samples':len(warm)}
    report={'data_version':dataset['data_version'],'gallery_skus':20,'concurrency':1,'transport':'FastAPI TestClient real multipart request/DB/log commit; excludes TCP/TLS and external network',
        'system_load':'Other OS/application load is not controlled. This is a local small-sample measurement, not production acceptance.',
        'platform':platform.platform(),'python':platform.python_version(),'summary':summary,'requests':rows}
    path=ROOT/'.qa/m4-benchmark/api-latency.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(summary);print('Recorded:',path)


if __name__=='__main__':main()
