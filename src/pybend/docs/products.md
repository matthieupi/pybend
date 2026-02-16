# `products` Model

**Endpoint**: `GET /products` (returns schema)

## Fields

| Name | Type | Required | Default |
|------|------|----------|---------|
| name | string | Yes | — |
| price | number | Yes | — |
| description | string | No |  |
| comments | object | No | [] |
| id | object | No | None |

## Routes
### `/comment` [POST] (instancemethod)
**Method**: `comment`
#### Parameters:
- `comment`: *$ref*
**Returns**: `string`
