import unittest
import test_crud


class RoutingApiTests(unittest.TestCase):
    setUp = test_crud.CrudTests.setUp
    tearDown = test_crud.CrudTests.tearDown

    def test_create_duplicate_and_reads(self):
        batch = self.client.post('/produce', json=self.produce | {'risk_level':'CRITICAL'}).json()['id']
        before = self.client.get(f'/produce/{batch}').json()
        first = self.client.post(f'/produce/{batch}/rerouting')
        self.assertEqual(first.status_code,200,first.text)
        case = first.json()
        self.assertEqual(case['quantity_kg'],'1000.000')
        self.assertEqual(case['risk_level_at_creation'],'CRITICAL')
        self.assertEqual(case['status'],'AWAITING_ALTERNATIVE_MATCH')
        self.assertTrue(case['trigger_details']['reasons'])
        self.assertTrue(case['trigger_reason'])
        second = self.client.post(f'/produce/{batch}/rerouting')
        self.assertEqual(second.status_code,200)
        self.assertEqual(second.json(),case)
        self.assertEqual(self.client.get('/routing-cases').json(),[case])
        self.assertEqual(self.client.get(f'/routing-cases/{case["id"]}').json(),case)
        self.assertEqual(self.client.get(f'/produce/{batch}').json(),before)
        self.assertEqual(self.client.get('/transactions').json(),[])

    def test_ineligible_missing_and_empty(self):
        batch = self.client.post('/produce',json=self.produce).json()['id']
        self.assertEqual(self.client.post(f'/produce/{batch}/rerouting').status_code,409)
        self.assertEqual(self.client.post('/produce/999999/rerouting').status_code,404)
        self.assertEqual(self.client.get('/routing-cases/999999').status_code,404)
        self.assertEqual(self.client.get('/routing-cases').json(),[])

    def test_swagger_registration(self):
        paths=self.client.get('/openapi.json').json()['paths']
        for path,method in [('/produce/{batch_id}/rerouting','post'),('/routing-cases','get'),('/routing-cases/{case_id}','get')]:
            self.assertIn(method,paths[path])
            self.assertEqual(paths[path][method]['tags'],['Routing Cases'])
        self.assertEqual(self.client.get('/docs').status_code,200)
