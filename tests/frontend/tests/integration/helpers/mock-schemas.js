/**
 * Mock schemas that mirror real Product/Comment/Like backend schemas.
 * Used by integration tests to avoid network dependency.
 */

export const API_URL = 'http://localhost:5000';

export const CommentSchema = {
  $schema: `${API_URL}/Schema`,
  $id: `${API_URL}/Comment`,
  __name__: 'Comment',
  __tablename__: 'comments',
  type: 'object',
  required: ['name'],
  properties: {
    id: { type: 'integer', title: 'ID', readOnly: true, ui: { display: false } },
    name: { type: 'string', title: 'Name', minLength: 1, maxLength: 200 },
    description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
    user_owner: { type: 'integer', title: 'Author', ui: { display: false } },
    parent_id: { type: 'selfref', title: 'Parent', default: null },
    likes: {
      type: 'array',
      title: 'Likes',
      items: { anyOf: [{ $ref: '#/$defs/Like' }, { type: 'null' }] },
      default: [],
    },
  },
  ui: {
    field_order: ['name', 'description', 'likes'],
    renderer: { item: 'ntx-item', list: 'ntx-list' },
  },
  access: {
    read: { rule: 'anyone' },
    create: { rule: 'authenticated' },
    update: { op: 'or', rules: [{ rule: 'owner', field: 'user_owner' }, { rule: 'role', roles: ['admin'] }] },
    delete: { op: 'or', rules: [{ rule: 'owner', field: 'user_owner' }, { rule: 'role', roles: ['admin'] }] },
  },
  methods: {
    reply: {
      route: '/reply',
      methods: ['POST'],
      scope: 'instancemethod',
      title: 'Reply',
      parameters: {
        comment: { type: '$ref', $ref: '#/$defs/Comment' },
      },
      returns: 'string',
      ui: { layout: 'inline', placeholder: 'Write a reply...', button_label: 'Reply' },
    },
  },
  $defs: {},
};

export const LikeSchema = {
  $schema: `${API_URL}/Schema`,
  $id: `${API_URL}/Like`,
  __name__: 'Like',
  __tablename__: 'likes',
  type: 'object',
  properties: {
    id: { type: 'integer', title: 'ID', readOnly: true, ui: { display: false } },
    user: { type: 'integer', title: 'User' },
    created_at: { type: 'string', title: 'Created At' },
  },
  ui: { renderer: { item: 'ntx-item' } },
  access: { read: { rule: 'anyone' }, create: { rule: 'authenticated' } },
  methods: {},
  $defs: {},
};

export const ProductSchema = {
  $schema: `${API_URL}/Schema`,
  $id: `${API_URL}/Product`,
  __name__: 'Product',
  __tablename__: 'products',
  type: 'object',
  required: ['name', 'price'],
  properties: {
    id: { type: 'integer', title: 'ID', readOnly: true, ui: { display: false } },
    name: {
      type: 'string',
      title: 'Name',
      minLength: 1,
      maxLength: 200,
      ui: { placeholder: 'Product name...' },
    },
    price: {
      type: 'number',
      title: 'Price',
      exclusiveMinimum: 0,
      ui: { widget: 'currency' },
      access: { view: 'anyone', edit: 'admin' },
    },
    description: {
      type: 'string',
      title: 'Description',
      default: '',
      ui: { widget: 'textarea' },
    },
    image: { type: 'string', title: 'Image', ui: { display: false } },
    user_owner: { type: 'integer', title: 'Owner', ui: { display: false, protected: true } },
    comments: {
      type: 'array',
      title: 'Comments',
      items: { anyOf: [{ $ref: '#/$defs/Comment' }, { type: 'null' }] },
      default: [],
    },
    likes: {
      type: 'array',
      title: 'Likes',
      items: { anyOf: [{ $ref: '#/$defs/Like' }, { type: 'null' }] },
      default: [],
    },
  },
  ui: {
    field_order: ['name', 'price', 'description', 'comments', 'likes'],
    groups: { main: ['name', 'description', 'price'], Social: ['comments', 'likes'] },
    renderer: { item: 'ntx-item', list: 'ntx-list' },
    populate: { depth: 1 },
  },
  access: {
    read: { rule: 'anyone' },
    create: { rule: 'authenticated' },
    update: { op: 'or', rules: [{ rule: 'owner', field: 'user_owner' }, { rule: 'role', roles: ['admin'] }] },
    delete: { rule: 'role', roles: ['admin'] },
  },
  methods: {
    comment: {
      route: '/comment',
      methods: ['POST'],
      scope: 'instancemethod',
      title: 'Comment',
      parameters: {
        comment: { type: '$ref', $ref: '#/$defs/Comment' },
      },
      returns: 'string',
      access: { rule: 'authenticated' },
      ui: { layout: 'inline', attach_to: 'comments', placeholder: 'Write a comment...', button_label: 'Comment' },
    },
    like: {
      route: '/like',
      methods: ['POST'],
      scope: 'instancemethod',
      title: 'Like',
      parameters: {},
      returns: 'string',
      access: { rule: 'authenticated' },
      ui: { layout: 'button', icon: 'heart', count_field: 'likes' },
    },
  },
  $defs: {
    Comment: { ...CommentSchema, $id: `${API_URL}/Comment` },
    Like: { ...LikeSchema, $id: `${API_URL}/Like` },
  },
};

export function makeProductData(id = 1) {
  return {
    id,
    $schema: `${API_URL}/Product`,
    $id: `${API_URL}/products/${id}`,
    name: `Test Product ${id}`,
    price: 29.99,
    description: 'A test product',
    image: '',
    user_owner: 1,
    comments: [],
    likes: [],
  };
}

export function makeCommentData(id = 1, productId = 1) {
  return {
    id,
    $schema: `${API_URL}/Comment`,
    $id: `${API_URL}/products/${productId}/comments/${id}`,
    name: `Test Comment ${id}`,
    description: 'A test comment',
    user_owner: 1,
    parent_id: null,
    likes: [],
  };
}

export function makeLikeData(id = 1) {
  return {
    id,
    $schema: `${API_URL}/Like`,
    $id: `${API_URL}/likes/${id}`,
    user: 1,
    created_at: new Date().toISOString(),
  };
}

export function makeProductListResponse(count = 3) {
  const data = [];
  for (let i = 1; i <= count; i++) {
    data.push(makeProductData(i));
  }
  return {
    data,
    meta: { total: count, limit: 20, offset: 0, has_more: false },
  };
}
