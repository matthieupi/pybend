# `products_comments` Model

**Endpoint**: `GET /products_comments` (returns schema)

## Fields

| Name | Type | Required | Default |
|------|------|----------|---------|
| name | string | Yes | — |
| description | string | No |  |
| user_owner | integer | No | None |
| replies | object | No | [] |
| likes | object | No | [] |
| id | object | No | None |
| product_id | integer | Yes | — |

## Routes