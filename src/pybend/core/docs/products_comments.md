# `products_comments` Model

**Endpoint**: `GET /products_comments` (returns schema)

## Fields

| Name | Type | Required | Default |
|------|------|----------|---------|
| id | integer | No | 0 |
| image | string | No |  |
| name | string | Yes | — |
| description | string | No |  |
| user_owner | integer | No | None |
| parent_id | selfref | No | — |
| likes | array | No | [] |
| product_id | integer | Yes | — |

## Routes
### `/like` [POST] (instancemethod)
**Method**: `like`
#### Parameters:
- `like`: *$ref*
**Returns**: `string`
