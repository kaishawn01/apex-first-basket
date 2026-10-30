"""Phase 8 authorized synthetic test, using the unchanged Phase 7 model protocol."""
import argparse
import json
from unittest.mock import patch
import phase7_fixture
import updater


def exercise(path, action):
    release = updater.current_version()
    # Fixture only: the archived model remains 3.0.6, not a new experiment.
    # This override must never be used to disguise a real model version.
    with patch.object(updater, 'current_version', return_value='3.0.6'):
        report = phase7_fixture.exercise(path, action)
    return {**report, 'test_only': True, 'execution_release': release,
            'model_protocol': 'apex-v3.0.6-live-01', 'live_provider_calls': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['generate', 'grade'])
    p.add_argument('--journal', required=True)
    a = p.parse_args()
    print(json.dumps(exercise(a.journal, a.action), indent=2))
