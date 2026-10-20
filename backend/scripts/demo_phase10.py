"""Dedicated synthetic demo records; never alter live produce batch 1."""
import json
import sys
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen

base=(sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8000').rstrip('/')


def api(path,payload=None,key=None):
    headers={'Content-Type':'application/json'}
    if key:
        headers['Idempotency-Key']=key
    request=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    with urlopen(request,timeout=30) as response:
        return json.load(response)


def user(name,email,role):
    existing=next((row for row in api('/users') if row['email']==email),None)
    return existing or api('/users',{'name':name,'email':email,'role':role,'location_name':'Puducherry'})


def main():
    live_before=api('/produce/1')
    readiness_before=api('/produce/1/routing-readiness')
    assert live_before['remaining_quantity_kg']=='150.000' and not readiness_before['rerouting_candidate']
    farmer=user('Phase 10 Synthetic Farmer','phase10.farmer@agriroute.demo','FARMER')
    buyer=user('Phase 10 Synthetic Primary Buyer','phase10.buyer@agriroute.demo','BUYER')
    processor=user('Phase 10 Synthetic Processor','phase10.processor@agriroute.demo','PROCESSOR')
    today=datetime.now(timezone(timedelta(hours=5,minutes=30))).date()
    batch=next((row for row in api(f'/produce?farmer_id={farmer["id"]}') if row['notes']=='PHASE10_ISOLATED_SYNTHETIC_DEMO'),None)
    if batch is None:
        batch=api('/produce',{'farmer_id':farmer['id'],'crop_name':'Tomato','initial_quantity_kg':'1000','expected_price_per_kg':'25','harvest_date':today.isoformat(),'available_until':(today+timedelta(days=1)).isoformat(),'quality_grade':'A','risk_level':'CRITICAL','visible_condition':'FRESH','notes':'PHASE10_ISOLATED_SYNTHETIC_DEMO','latitude':'11.9416','longitude':'79.8083','location_name':'Puducherry'})
    assert batch['id']!=1
    if batch['sold_quantity_kg']=='0.000':
        requirement=api('/buyer-requirements',{'buyer_id':buyer['id'],'crop_name':'Tomato','required_quantity_kg':'850','minimum_quality':'A','minimum_price_per_kg':'20','maximum_price_per_kg':'30'})
        api('/transactions/accept',{'produce_batch_id':batch['id'],'buyer_requirement_id':requirement['id'],'quantity_kg':'850','price_per_kg':'25'})
    case=next((row for row in api('/routing-cases') if row['produce_batch_id']==batch['id']),None)
    if case is None:
        case=api(f'/produce/{batch["id"]}/rerouting',{})
    requirements=api(f'/processor-requirements?processor_id={processor["id"]}')
    requirement=requirements[0] if requirements else api('/processor-requirements',{'processor_id':processor['id'],'crop_name':'Tomato','required_quantity_kg':'150','minimum_acceptable_quality':'B','acceptable_produce_conditions':['FRESH'],'intended_utilization':'FOOD_PROCESSING','minimum_price_per_kg':'15','maximum_price_per_kg':'30','maximum_distance_km':'50','pickup_date':today.isoformat(),'location_name':'Puducherry','latitude':'11.9450','longitude':'79.8100'})
    allocations=api(f'/alternative-allocations?routing_case_id={case["id"]}')
    before=api(f'/produce/{batch["id"]}')
    if not allocations:
        assessment=api(f'/routing-cases/{case["id"]}/suitability',{'intended_utilization':'FOOD_PROCESSING','confirmed_condition':'FRESH','suitable':True,'assessed_by':'Phase 10 synthetic fixture assessor','assessment_notes':'Synthetic isolated demonstration only; no real produce safety, delivery, or utilization is asserted.'})
        matches=api(f'/routing-cases/{case["id"]}/processor-matches')
        assert any(row['processor_requirement_id']==requirement['id'] and row['compatible_quantity_kg']=='150.000' for row in matches['matches'])
        assert api(f'/produce/{batch["id"]}')==before
        allocation=api(f'/routing-cases/{case["id"]}/accept',{'processor_requirement_id':requirement['id'],'accepted_quantity_kg':'150','price_per_kg':'20'},'phase10-synthetic-150')
    else:
        matches={'matches':[],'note':'Demo allocation already exists; no repeated allocation performed.'}
        allocation=allocations[0]
    after=api(f'/produce/{batch["id"]}')
    case_after=api(f'/routing-cases/{case["id"]}')
    assert after['initial_quantity_kg']=='1000.000' and after['sold_quantity_kg']=='850.000' and after['remaining_quantity_kg']=='0.000' and after['rerouted_quantity_kg']=='150.000'
    assert case_after['status']=='COMPLETED'
    assert api('/produce/1')==live_before and api('/produce/1/routing-readiness')==readiness_before
    print(json.dumps({'demo_batch_id':batch['id'],'demo_batch_code':after['batch_code'],'processor_id':processor['id'],'processor_requirement_id':requirement['id'],'routing_case_id':case['id'],'matches_before':matches,'allocation':allocation,'inventory_before':{key:before[key] for key in ('initial_quantity_kg','sold_quantity_kg','remaining_quantity_kg','rerouted_quantity_kg')},'inventory_after':{key:after[key] for key in ('initial_quantity_kg','sold_quantity_kg','remaining_quantity_kg','rerouted_quantity_kg')},'routing_case_status':case_after['status'],'live_batch_1_unchanged':True},indent=2))


if __name__=='__main__':
    main()
