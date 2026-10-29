"""Offline comparison. Metrics require two completed human reviews and adjudication."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/api'))
from app.image_features import COLOR_VERSION,DEEP_VERSION,ResnetEncoder,color_vector,decode_image


def read_json(path):return json.loads(path.read_text(encoding='utf-8'))


def read_labels(dataset,a,b,adjudication=None):
    if not all(isinstance(doc,dict) and isinstance(doc.get('reviewer'),str) and doc['reviewer'].strip() for doc in [a,b]):
        raise ValueError('Two distinct named human reviewers are required')
    if a['reviewer'].strip()==b['reviewer'].strip():
        raise ValueError('Two distinct named human reviewers are required')
    codes={g['sku_code'] for g in dataset['gallery']}
    expected={q['id'] for q in dataset['queries']}
    for document in [a,b]+([adjudication] if adjudication else []):
        if document.get('data_version')!=dataset['data_version']:raise ValueError('Annotation dataset version mismatch')
        entries=document.get('queries',[])
        if len(entries)!=len(expected) or {x['query_id'] for x in entries}!=expected:raise ValueError('Incomplete or duplicate query annotations')
    results={}
    for qid in sorted(expected):
        left=next(q for q in a['queries'] if q['query_id']==qid)
        right=next(q for q in b['queries'] if q['query_id']==qid)
        for row in [left,right]:
            if row.get('duplicate_checked') is not True:raise ValueError('Human duplicate review is incomplete: '+qid)
            if set(row.get('ratings',{}))!=codes:raise ValueError('Missing or unexpected gallery SKU: '+qid)
            if not row.get('exclude_reason','').strip() and any(type(x) is not int or x not in (0,1,2) for x in row['ratings'].values()):
                raise ValueError('Human relevance ratings are incomplete: '+qid)
        agreement=left['ratings']==right['ratings'] and left.get('exclude_reason','').strip()==right.get('exclude_reason','').strip()
        if agreement:final=left
        else:
            if not adjudication or not isinstance(adjudication.get('reviewer'),str) or not adjudication['reviewer'].strip() or adjudication['reviewer'].strip() in {a['reviewer'].strip(),b['reviewer'].strip()}:
                raise ValueError('Independent adjudication is required for disagreements: '+qid)
            final=next(q for q in adjudication['queries'] if q['query_id']==qid)
            if not final.get('decision_reason','').strip() or final.get('duplicate_checked') is not True:raise ValueError('Adjudication reason or duplicate review missing: '+qid)
            if set(final.get('ratings',{}))!=codes:raise ValueError('Adjudicated SKU set mismatch')
            if not final.get('exclude_reason','').strip() and any(type(x) is not int or x not in (0,1,2) for x in final['ratings'].values()):raise ValueError('Adjudication is incomplete')
        results[qid]=None if final.get('exclude_reason','').strip() else {code for code,grade in final['ratings'].items() if grade==2}
    return results


def metrics(predictions,relevance,k=5):
    recalls=[];precisions=[];empty=0;excluded=0
    for qid,ranking in predictions.items():
        truth=relevance[qid]
        if truth is None:excluded+=1;continue
        retrieved=ranking[:k]
        if len(set(retrieved))!=len(retrieved):raise ValueError('Duplicate SKU in ranking')
        hits=len(set(retrieved)&truth)
        precisions.append(hits/k)
        if truth:recalls.append(hits/len(truth))
        else:empty+=1
    return {'recall_at_5':float(np.mean(recalls)) if recalls else None,
        'precision_at_5':float(np.mean(precisions)) if precisions else None,
        'positive_queries':len(recalls),'no_match_queries':empty,'excluded_queries':excluded,
        'precision_denominator':'5 per non-excluded query, including no-match queries',
        'recall_denominator':'strong-relevant SKUs; no-match queries excluded from recall mean'}


def verified_image(row):
    path=(ROOT/row['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('Image path outside project')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Frozen image changed: '+row['path'])
    return decode_image(raw)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=ROOT/'assets/image_search_benchmark/dataset.json')
    p.add_argument('--review-a',type=Path);p.add_argument('--review-b',type=Path);p.add_argument('--adjudication',type=Path)
    p.add_argument('--predict-only',action='store_true');p.add_argument('--split',choices=['dev','test'],default='test')
    p.add_argument('--output',type=Path,default=ROOT/'.qa/m4-benchmark')
    args=p.parse_args();dataset=read_json(args.dataset)
    canonical={k:v for k,v in dataset.items() if k!='data_version'}
    if sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=dataset['data_version']:
        p.error('Frozen dataset manifest changed')
    relevance=None
    try:
        if not args.predict_only:
            if not args.review_a or not args.review_b:raise ValueError('Supply completed --review-a and --review-b, or explicitly choose --predict-only (no relevance metrics)')
            relevance=read_labels(dataset,read_json(args.review_a),read_json(args.review_b),read_json(args.adjudication) if args.adjudication else None)
    except ValueError as exc:p.error(str(exc))
    model=ResnetEncoder(ROOT/'apps/api/.local/models/resnet18-f37072fd.pth')
    gallery=[verified_image(g) for g in dataset['gallery']]
    start=time.perf_counter();deep=np.stack([model.encode(i) for i in gallery]);color=np.stack([color_vector(i) for i in gallery])
    build_ms=(time.perf_counter()-start)*1000
    rows=[q for q in dataset['queries'] if q['split']==args.split]
    methods={'deep':(deep,model.encode),'color':(color,color_vector)}
    report={'validation_status':'human_annotated' if relevance is not None else 'awaiting_human_annotations',
        'data_version':dataset['data_version'],'split':args.split,'query_count':len(rows),'gallery_skus':len(gallery),
        'weights_sha256':model.weights_sha256,'algorithms':{'deep':DEEP_VERSION,'color':COLOR_VERSION},
        'environment':model.runtime|{'python':platform.python_version(),'platform':platform.platform(),'numpy':np.__version__},
        'gallery_build_ms':round(build_ms,3),'timing_scope':'warm offline query decode + feature + exact matrix ranking; excludes HTTP, DB and index load',
        'relevance_metrics':None,'methods':{},'raw_rankings':{}}
    # One gallery-based warmup per method; no query labels or query tuning.
    for method,(matrix,encode) in methods.items():
        encode(gallery[0]);rankings={};timings=[];raw=[]
        for q in rows:
            tick=time.perf_counter();vector=encode(verified_image(q));scores=matrix@vector
            order=sorted(range(len(gallery)),key=lambda i:(-float(scores[i]),dataset['gallery'][i]['sku_code']))
            elapsed=(time.perf_counter()-tick)*1000;timings.append(elapsed)
            ranking=[dataset['gallery'][i]['sku_code'] for i in order[:5]];rankings[q['id']]=ranking
            raw.append({'query_id':q['id'],'elapsed_ms':round(elapsed,3),'top5':[{'sku_code':dataset['gallery'][i]['sku_code'],'score':round(float(scores[i]),6)} for i in order[:5]]})
        report['methods'][method]={'offline_p95_ms':round(float(np.percentile(timings,95)),3),'samples':len(timings)}
        if relevance is not None:
            if report['relevance_metrics'] is None:report['relevance_metrics']={}
            report['relevance_metrics'][method]=metrics(rankings,relevance)
        report['raw_rankings'][method]=raw
    if relevance is not None:
        report['annotation_sha256']={name:sha256(path.read_bytes()).hexdigest() for name,path in [('review_a',args.review_a),('review_b',args.review_b),('adjudication',args.adjudication)] if path}
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/f'{args.split}-comparison.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Recorded:',target);print('Status:',report['validation_status']);print('Methods:',report['methods'])


if __name__=='__main__':main()
