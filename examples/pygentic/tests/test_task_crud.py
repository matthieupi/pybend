"""CRUD tests for the Task model."""
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration


class TestTaskCRUD:
    def test_list_tasks_public(self, client, seed_data):
        resp = client.get('/tasks')
        assert resp.status_code == 200
        data = resp.json()
        # Level 3 (actor routing) returns a plain list; Level 1/2 returns {data: [...]}
        items = data['data'] if isinstance(data, dict) and 'data' in data else data
        assert isinstance(items, list)
        assert len(items) >= 2

    def test_create_task_requires_auth(self, client):
        resp = client.post('/tasks', json={'title': 'Test'})
        assert resp.status_code in (401, 403)

    def test_create_task(self, client, alice_token):
        resp = client.post(
            '/tasks',
            json={'title': 'New task', 'priority': 'high'},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['title'] == 'New task'

    def test_get_task(self, client, seed_data):
        task_id = seed_data['tasks'][0].id
        resp = client.get(f'/tasks/{task_id}')
        assert resp.status_code == 200
