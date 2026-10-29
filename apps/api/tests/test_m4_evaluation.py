from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.evaluate_image_search import metrics,read_labels


def annotations():
    dataset={'data_version':'frozen-test','gallery':[{'sku_code':'A'},{'sku_code':'B'}],'queries':[{'id':'Q1'}]}
    a={'data_version':'frozen-test','reviewer':'member-a','queries':[{'query_id':'Q1','duplicate_checked':True,
        'exclude_reason':'','decision_reason':'','ratings':{'A':2,'B':0}}]}
    b=deepcopy(a);b['reviewer']='member-b'
    return dataset,a,b


def test_metrics_fixed_k_no_match_and_excluded_queries():
    result=metrics({'positive':['A','C','D','E','F'],'no-match':['X'],'excluded':['Y']},
        {'positive':{'A','B'},'no-match':set(),'excluded':None})
    assert result['recall_at_5']==.5 and result['precision_at_5']==.1
    assert result['positive_queries']==1 and result['no_match_queries']==1 and result['excluded_queries']==1


def test_incomplete_or_same_reviewer_is_rejected():
    dataset,a,b=annotations()
    b['queries'][0]['ratings']['B']=None
    with pytest.raises(ValueError,match='incomplete'):read_labels(dataset,a,b)
    b=deepcopy(a)
    with pytest.raises(ValueError,match='distinct'):read_labels(dataset,a,b)
    b['reviewer']='member-b';b['queries'][0]['duplicate_checked']=False
    with pytest.raises(ValueError,match='duplicate review'):read_labels(dataset,a,b)


def test_disagreement_requires_independent_adjudication():
    dataset,a,b=annotations();b['queries'][0]['ratings']['B']=2
    with pytest.raises(ValueError,match='adjudication'):read_labels(dataset,a,b)
    final=deepcopy(a);final['reviewer']='member-c';final['queries'][0]['decision_reason']='Clear structure match only for A'
    assert read_labels(dataset,a,b,final)=={'Q1':{'A'}}


def test_versions_and_sku_sets_cannot_drift():
    dataset,a,b=annotations();b['data_version']='changed'
    with pytest.raises(ValueError,match='version'):read_labels(dataset,a,b)
    b['data_version']='frozen-test';del b['queries'][0]['ratings']['B']
    with pytest.raises(ValueError,match='SKU'):read_labels(dataset,a,b)
