"""Pure synthetic tests for the reversible local Phase 10 candidate audit fix."""
import unittest
import phase10_dunk as d
from test_phase10 import fixture

class LocalCandidateFixTests(unittest.TestCase):
    def setUp(self):
        self.box, pages = fixture()
        for e in pages[0]["plays"]:
            e["type"] = "Start Period" if e["seq"] == 1 else "End Period"
            if e["shot"]:
                ft = e["shot"]["points_attempted"] == 1
                e["type"] = "Free Throw" if ft else "Jump Shot"
                e["shot"]["zone"] = "free_throw" if ft else "paint"
        self.payload = {"data": pages[0]}
    def report(self):
        return d.validate_event_semantics(self.box,self.payload,'2026-10-29')

    def test_unrelated_unknown_label_does_not_poison_candidate(self):
        self.payload['data']['plays'][0]['type']='UNKNOWN LOCAL TIMEOUT'
        result=self.report()
        self.assertIn('unreviewed_event_type',result['blockers'])
        self.assertEqual(result['first_score']['status'],'CANDIDATE_ONLY')
        self.assertTrue(result['first_score']['consistent_under_checked_fields'])
        self.assertEqual(result['first_score']['candidate_specific_blockers'],[])
        self.assertFalse(result['interpretation_validated'])
        self.assertFalse(result['training_enabled'])
        self.assertFalse(result['model_compatible'])

    def test_observed_free_throw_label_but_not_role_verified(self):
        self.payload['data']['plays'][1]['type']='Free Throw - 1 of 1'
        self.payload['data']['plays'][2]['type']='Cutting Layup Shot'
        result=self.report()
        self.assertEqual(result['aggregate']['observed_shape_checked_label_categories'],
                         {'free_throw':1,'field_goal':1})
        self.assertNotIn('free_throw_type_unreviewed',result['blockers'])
        self.assertTrue(result['first_score']['consistent_under_checked_fields'])
        self.assertEqual(result['first_score']['credited_shooter_role'].split(':')[0], 'UNVERIFIED')
        self.assertEqual(result['opening_tip']['status'],'UNRESOLVED')
        self.assertEqual(result['first_possession']['status'],'UNRESOLVED')

    def test_bad_label_shot_pair_is_still_blocked(self):
        self.payload['data']['plays'][2]['type']='Free Throw - 1 of 2'
        result=self.report()
        self.assertIn('observed_label_shape_conflict',result['blockers'])
        self.assertFalse(result['interpretation_validated'])

    def test_missing_scorer_fails_candidate_numeric_checks(self):
        self.payload['data']['plays'][1]['player_id']=None
        result=self.report()
        self.assertFalse(result['first_score']['consistent_under_checked_fields'])
        self.assertIn('candidate_actor_or_team_unresolved',
                      result['first_score']['candidate_specific_blockers'])

    def test_invalid_free_throw_fraction_is_blocked(self):
        self.payload['data']['plays'][1]['type']='Free Throw - 3 of 2'
        result=self.report()
        self.assertIn('observed_label_shape_conflict',result['blockers'])
        self.assertFalse(result['interpretation_validated'])


    def test_second_batch_exact_labels_and_shapes(self):
        self.assertEqual(
            d._phase10_observed_label_class(
                'Tip Shot', {'points_attempted': 2}),
            'field_goal')
        self.assertEqual(
            d._phase10_observed_label_class(
                'Offensive Foul Turnover', None),
            'nonshot')
        self.assertEqual(
            d._phase10_observed_label_class(
                'Tip Shot', None),
            'conflict')
        self.assertEqual(
            d._phase10_observed_label_class(
                'Shot Clock Turnover', {'points_attempted': 2}),
            'conflict')
        self.assertIsNone(
            d._phase10_observed_label_class(
                'UNKNOWN PROVIDER EVENT', None))

    def test_second_batch_never_promotes_model(self):
        self.payload['data']['plays'][0]['type'] = 'Offensive Foul Turnover'
        self.payload['data']['plays'][2]['type'] = 'Putback Dunk Shot'
        result = self.report()
        self.assertNotIn('unreviewed_event_type', result['blockers'])
        self.assertEqual(result['first_score']['status'], 'CANDIDATE_ONLY')
        self.assertFalse(result['interpretation_validated'])
        self.assertFalse(result['model_compatible'])
        self.assertFalse(result['training_enabled'])

if __name__ == '__main__': unittest.main()
