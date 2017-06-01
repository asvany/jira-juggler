#!/usr/bin/python
# -*- coding: utf-8 -*-

# python -m unittest discover -s scripts/ -p '*_test.py'

import json
from collections import namedtuple

import unittest

try:
    from unittest.mock import MagicMock, patch, call
except ImportError as err:
    print("unittest.mock import failed")
    try:
        from mock import MagicMock, patch, call
    except ImportError as err:
        print("mock import failed. installing mock")
        import pip
        pip.main(['install', 'mock'])
        from mock import MagicMock, patch, call

try:
    from jira import JIRA, JIRAError
except ImportError as err:
    print("jira import failed")
    import pip
    pip.main(['install', 'jira'])
    from jira import JIRA, JIRAError

from jira_juggler import jira_juggler as dut

class TestJiraJuggler(unittest.TestCase):
    '''Testing JiraJuggler interface'''

    URL = 'http://my-non-existing-jira.melexis.com'
    USER = 'justme'
    PASSWD = 'myuselesspassword'
    QUERY = 'some random query'
    SECS_PER_DAY = 8.0 * 60 * 60

    KEY1 = 'Issue1'
    SUMMARY1 = 'Some random description of issue 1'
    ASSIGNEE1 = 'John Doe'
    ESTIMATE1 = 0.3 * SECS_PER_DAY
    DEPENDS1 = None

    KEY2 = 'Issue2'
    SUMMARY2 = 'Some random description of issue 2'
    ASSIGNEE2 = 'Jane Doe'
    ESTIMATE2 = 1.2 * SECS_PER_DAY
    DEPENDS2 = KEY1

    JIRA_JSON_ISSUE_TEMPLATE = '''{{
        "key": "{key}",
        "fields": {{
            "summary": "{summary}",
            "assignee": {{
                "name": "{assignee}"
            }},
            "aggregatetimeoriginalestimate": {estimate},
            "issuelinks": [
                {{
                    "inwardIssue": {{
                        "key": "{depends}"
                    }},
                    "type": {{
                        "name": "Blocker"
                    }}
                }}
            ]
        }}
    }}'''

    def SetUp(self):
        '''SetUp is run before each test to provide clean working environment'''

    @patch('jira_juggler.jira_juggler.JIRA', autospec=True)
    def test_empty_query_result(self, jira_mock):
        '''Test for Jira not returning any task on the given query'''
        jira_mock_object = MagicMock(spec=JIRA)
        jira_mock.return_value = jira_mock_object
        juggler = dut.JiraJuggler(self.URL, self.USER, self.PASSWD, self.QUERY)
        self.assertEqual(self.QUERY, juggler.query)

        jira_mock_object.search_issues.return_value = []
        juggler.juggle()
        jira_mock_object.search_issues.assert_called_once_with(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=0)


    @patch('jira_juggler.jira_juggler.JIRA', autospec=True)
    def test_single_task_happy(self, jira_mock):
        '''Test for simple happy flow: single task is returned by Jira'''
        jira_mock_object = MagicMock(spec=JIRA)
        jira_mock.return_value = jira_mock_object
        juggler = dut.JiraJuggler(self.URL, self.USER, self.PASSWD, self.QUERY)
        self.assertEqual(self.QUERY, juggler.query)

        jira_mock_object.search_issues.side_effect = [[self._mock_jira_issue(self.KEY1,
                                                                             self.SUMMARY1,
                                                                             self.ASSIGNEE1,
                                                                             self.ESTIMATE1,
                                                                             self.DEPENDS1)
                                                       ], []]
        issues = juggler.juggle()
        jira_mock_object.search_issues.assert_has_calls([call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=0),
                                                         call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=1)])
        self.assertEqual(1, len(issues))
        self.assertEqual(self.KEY1, issues[0].key)
        self.assertEqual(self.SUMMARY1, issues[0].summary)
        self.assertEqual(self.ASSIGNEE1, issues[0].properties['allocate'].get_value())
        self.assertEqual(self.ESTIMATE1/self.SECS_PER_DAY, issues[0].properties['effort'].get_value())
        self.assertEqual([], issues[0].properties['depends'].get_value())

    @patch('jira_juggler.jira_juggler.JIRA', autospec=True)
    def test_single_task_minimal(self, jira_mock):
        '''Test for minimal happy flow: single task with minimal content is returned by Jira'''
        jira_mock_object = MagicMock(spec=JIRA)
        jira_mock.return_value = jira_mock_object
        juggler = dut.JiraJuggler(self.URL, self.USER, self.PASSWD, self.QUERY)
        self.assertEqual(self.QUERY, juggler.query)

        jira_mock_object.search_issues.side_effect = [[self._mock_jira_issue(self.KEY1,
                                                                             self.SUMMARY1,
                                                                             None,
                                                                             self.ESTIMATE1, #TODO: None here
                                                                             None),
                                                       ], []]
        issues = juggler.juggle()
        jira_mock_object.search_issues.assert_has_calls([call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=0),
                                                         call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=1)])
        self.assertEqual(1, len(issues))
        self.assertEqual(self.KEY1, issues[0].key)
        self.assertEqual(self.SUMMARY1, issues[0].summary)


    @patch('jira_juggler.jira_juggler.JIRA', autospec=True)
    def test_task_depends(self, jira_mock):
        '''Test for dual happy flow: one task depends on the other'''
        jira_mock_object = MagicMock(spec=JIRA)
        jira_mock.return_value = jira_mock_object
        juggler = dut.JiraJuggler(self.URL, self.USER, self.PASSWD, self.QUERY)
        self.assertEqual(self.QUERY, juggler.query)

        jira_mock_object.search_issues.side_effect = [[self._mock_jira_issue(self.KEY1,
                                                                             self.SUMMARY1,
                                                                             self.ASSIGNEE1,
                                                                             self.ESTIMATE1,
                                                                             self.DEPENDS1),
                                                       self._mock_jira_issue(self.KEY2,
                                                                             self.SUMMARY2,
                                                                             self.ASSIGNEE2,
                                                                             self.ESTIMATE2,
                                                                             self.DEPENDS2),
                                                       ], []]
        issues = juggler.juggle()
        jira_mock_object.search_issues.assert_has_calls([call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=0),
                                                         call(self.QUERY, maxResults=dut.JIRA_PAGE_SIZE, startAt=2)])
        self.assertEqual(2, len(issues))
        self.assertEqual(self.KEY1, issues[0].key)
        self.assertEqual(self.SUMMARY1, issues[0].summary)
        self.assertEqual(self.ASSIGNEE1, issues[0].properties['allocate'].get_value())
        self.assertEqual(self.ESTIMATE1/self.SECS_PER_DAY, issues[0].properties['effort'].get_value())
        self.assertEqual([], issues[0].properties['depends'].get_value())
        self.assertEqual(self.KEY2, issues[1].key)
        self.assertEqual(self.SUMMARY2, issues[1].summary)
        self.assertEqual(self.ASSIGNEE2, issues[1].properties['allocate'].get_value())
        self.assertEqual(self.ESTIMATE2/self.SECS_PER_DAY, issues[1].properties['effort'].get_value())
        self.assertEqual(self.DEPENDS2, issues[1].properties['depends'].get_value()[0])

    def _mock_jira_issue(self, key, summary, assignee=None, estimate=None, depends=None):
        '''
        Helper function to create a mocked Jira issue

        Args:
            key (str): Key of the mocked Jira issue
            summary (str): Summary of the mocked Jira issue
            assignee (str): Name of the assignee of the mocked Jira issue
            estimate (float): Number of estimated seconds of the mocked Jira issue
            depends (float): Key of the issue on which the mocked Jira issue depends (blocked by relation)

        Returns:
            object: Mocked Jira Issue object
        '''
        data = self.JIRA_JSON_ISSUE_TEMPLATE.format(key=key,
                                                    summary=summary,
                                                    assignee=assignee,
                                                    estimate=estimate,
                                                    depends=depends)
        return json.loads(data, object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))

if __name__ == '__main__':
    unittest.main()
