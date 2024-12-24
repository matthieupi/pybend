# tests/test_api.py

def test_create_user(client):
    response = client.post('/users', json={
        'name': 'Charlie',
        'email': 'charlie@example.com',
        'age': 28
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Charlie'

def test_get_users(client):
    # Create a user first
    client.post('/users', json={
        'name': 'Dana',
        'email': 'dana@example.com',
        'age': 32
    })
    response = client.get('/users')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1

def test_user_login_success(client):
    # Create a user
    client.post('/users', json={
        'name': 'Eve',
        'email': 'eve@example.com',
        'age': 22
    })
    # Attempt to log in
    response = client.post('/users/login', json={'email': 'eve@example.com'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == 'Login successful'

def test_user_login_failure(client):
    response = client.post('/users/login', json={'email': 'nonexistent@example.com'})
    assert response.status_code == 401
    data = response.get_json()
    assert data['error'] == 'Invalid credentials'

def test_product_list(client):
    response = client.get('/products/list')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
