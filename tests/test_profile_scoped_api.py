import asyncio
import unittest
from unittest.mock import patch

from backend.collectors.agents import AgentsState, AgentProcess
from backend.api.memory import get_memory
from backend.api.agents import get_agents


class ProfileScopedApiTests(unittest.TestCase):
    def test_memory_endpoint_uses_requested_profile_dir(self):
        with patch('backend.api.memory.resolve_profile_scope', return_value=('next', '/tmp/hermes-next')) as resolve_mock, \
             patch('backend.api.memory.collect_config') as config_mock, \
             patch('backend.api.memory.collect_memory') as memory_mock:
            config_mock.return_value = type('Config', (), {'memory_char_limit': 2200, 'user_char_limit': 1375})()
            memory_mock.return_value = (
                type('MemoryState', (), {'entries': [], 'total_chars': 0, 'max_chars': 2200, 'source': 'memory', 'capacity_pct': 0, 'entry_count': 0, 'count_by_category': lambda self: {}})(),
                type('UserState', (), {'entries': [], 'total_chars': 0, 'max_chars': 1375, 'source': 'user', 'capacity_pct': 0, 'entry_count': 0, 'count_by_category': lambda self: {}})(),
            )

            response = asyncio.run(get_memory(profile='next'))

        self.assertEqual(response['profile'], 'next')
        resolve_mock.assert_called_once_with('next')
        config_mock.assert_called_once_with('/tmp/hermes-next')
        memory_mock.assert_called_once_with('/tmp/hermes-next', memory_char_limit=2200, user_char_limit=1375)

    def test_agents_endpoint_filters_by_selected_profile(self):
        fake_agents = AgentsState(processes=[
            AgentProcess(name='hermes', binary='hermes', running=True, profile='next'),
            AgentProcess(name='hermes', binary='hermes', running=True, profile='default'),
            AgentProcess(name='codex', binary='codex', running=True, profile=None),
        ])

        with patch('backend.api.agents.resolve_profile_scope', return_value=('next', '/tmp/hermes-next')) as resolve_mock, \
             patch('backend.api.agents.collect_agents', return_value=fake_agents) as collect_mock:
            response = asyncio.run(get_agents(profile='next'))

        body = response
        self.assertEqual(body['profile'], 'next')
        resolve_mock.assert_called_once_with('next')
        collect_mock.assert_called_once_with('/tmp/hermes-next', 'next')


if __name__ == '__main__':
    unittest.main()
