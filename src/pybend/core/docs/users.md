# `users` Model

**Endpoint**: `GET /users` (returns schema)

## Fields

| Name | Type | Required | Default |
|------|------|----------|---------|
| id | integer | No | None |
| name | string | Yes | — |
| email | string | Yes | — |
| role | string | No | user |
| age | object | No | None |

## Routes
### `/login` [POST] (instancemethod)
**Method**: `login`
#### Parameters:
- `email`: *string*
- `password`: *string*
**Returns**: `string`

### `/register` [POST] (instancemethod)
**Method**: `register`
#### Parameters:
- `name`: *string*
- `email`: *string*
- `password`: *string*
**Returns**: `string`
