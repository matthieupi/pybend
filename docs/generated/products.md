# `products` Model

> Stale generated snapshot. The collection URL below is not the current schema
> endpoint. See [snapshot status and generator](index.md); use live class schema.

**Endpoint**: `GET /products` (returns schema)

## Fields

| Name | Type | Required | Default |
|------|------|----------|---------|
| id | integer | No | 0 |
| image | string | No | https://placehold.co/400x300/e2e8f0/64748b?text=No+Image |
| name | string | Yes | — |
| price | number | Yes | — |
| description | string | No |  |
| comments | array | No | [] |
| favorites | array | No | [] |

## Routes
### `/comment` [POST] (instancemethod)
**Method**: `comment`
#### Parameters:
- `comment`: *$ref*
**Returns**: `string`

### `/favorite` [POST] (instancemethod)
**Method**: `favorite`
#### Parameters:
- *(none)*
**Returns**: `string`
