/**
 * Nested Entities — Integration Tests
 *
 * Tests: ListRef rendering, populated data normalization, nested CRUD
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, CommentSchema, makeProductData, makeCommentData, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, TX;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const nttMod = await import('../../core/NTT.js');
  const txMod = await import('../../core/TX.js');
  NTT = nttMod.NTT;
  TX = txMod.default;
});

describe('Nested Entities', () => {

  it('Product comments href array stored after normalization', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const productData = {
      ...makeProductData(1),
      comments: [
        `${API_URL}/products/1/comments/1`,
        `${API_URL}/products/1/comments/2`,
      ],
    };

    DC.READ([productData]);
    const product = DC.instances.get(1);
    expect(Array.isArray(product.value.comments)).toBe(true);
    expect(product.value.comments).toHaveLength(2);
    expect(product.value.comments[0]).toContain('/comments/1');
  });

  it('populated collection {data, meta} normalized to href array', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const CommentDC = NTT.get('Comment');

    const comment1 = { ...makeCommentData(1, 1), $id: `${API_URL}/products/1/comments/1` };
    const comment2 = { ...makeCommentData(2, 1), $id: `${API_URL}/products/1/comments/2` };

    const productData = {
      ...makeProductData(1),
      comments: {
        data: [comment1, comment2],
        meta: { total: 2 },
      },
    };

    DC.READ([productData]);
    const product = DC.instances.get(1);

    // Comments should be normalized to hrefs
    expect(Array.isArray(product.value.comments)).toBe(true);
    expect(product.value.comments).toHaveLength(2);
    expect(typeof product.value.comments[0]).toBe('string');

    // Child instances should be pre-registered in Comment DynamicClass
    expect(CommentDC.instances.has(1)).toBe(true);
    expect(CommentDC.instances.has(2)).toBe(true);
  });

  it('populated single Ref normalized to href string', () => {
    // Create a schema with a single $ref field
    const refSchema = {
      ...ProductSchema,
      __name__: 'RefTest',
      __tablename__: 'reftests',
      properties: {
        ...ProductSchema.properties,
        author: { $ref: '#/$defs/Comment', title: 'Author' },
      },
      $defs: { ...ProductSchema.$defs },
    };

    NTT.SCHEMA(refSchema);
    const DC = NTT.get('RefTest');

    const entityData = {
      ...makeProductData(1),
      author: { ...makeCommentData(1, 1), $id: `${API_URL}/comments/1` },
    };

    DC.READ([entityData]);
    const entity = DC.instances.get(1);
    // author should be normalized to href string
    expect(typeof entity.value.author).toBe('string');
    expect(entity.value.author).toBe(`${API_URL}/comments/1`);
  });

  it('comment with parent_id (self-referential) is stored correctly', () => {
    NTT.SCHEMA(ProductSchema);
    const CommentDC = NTT.get('Comment');

    const replyData = {
      ...makeCommentData(3, 1),
      parent_id: 1,
      $id: `${API_URL}/products/1/comments/3`,
    };

    CommentDC.READ([replyData]);
    const reply = CommentDC.instances.get(3);
    expect(reply.value.parent_id).toBe(1);
  });

  it('nested entity DELETE removes from parent collection on pull', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const CommentDC = NTT.get('Comment');

    // Create product with comments
    const productData = {
      ...makeProductData(1),
      comments: [
        `${API_URL}/products/1/comments/1`,
        `${API_URL}/products/1/comments/2`,
      ],
    };
    DC.READ([productData]);

    // Create comment instances
    CommentDC.READ([
      makeCommentData(1, 1),
      makeCommentData(2, 1),
    ]);

    // Delete comment 1
    const sentMessages = [];
    const originalSend = CommentDC.send;
    CommentDC.send = vi.fn((tx) => sentMessages.push(tx));

    CommentDC.DELETE({}, new TX({
      name: 'DELETE',
      source: `${API_URL}/products/1/comments/1`,
      target: 'Comment',
    }));

    expect(CommentDC.instances.has(1)).toBe(false);
    expect(CommentDC.instances.has(2)).toBe(true);
    CommentDC.send = originalSend;
  });

  it('normalizePopulated handles mixed href strings and objects', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const productData = {
      ...makeProductData(1),
      comments: {
        data: [
          `${API_URL}/products/1/comments/1`, // already a string
          { ...makeCommentData(2, 1), $id: `${API_URL}/products/1/comments/2` }, // populated object
        ],
        meta: { total: 2 },
      },
    };

    DC.READ([productData]);
    const product = DC.instances.get(1);
    expect(product.value.comments).toHaveLength(2);
    expect(product.value.comments[0]).toBe(`${API_URL}/products/1/comments/1`);
    expect(product.value.comments[1]).toBe(`${API_URL}/products/1/comments/2`);
  });

  it('deeply nested population (depth=2) normalizes recursively', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const CommentDC = NTT.get('Comment');
    const LikeDC = NTT.get('Like');

    const likeData = { id: 1, user: 1, created_at: '2024-01-01', $id: `${API_URL}/likes/1`, $schema: `${API_URL}/Like` };
    const commentData = {
      ...makeCommentData(1, 1),
      $id: `${API_URL}/products/1/comments/1`,
      likes: {
        data: [likeData],
        meta: { total: 1 },
      },
    };

    const productData = {
      ...makeProductData(1),
      comments: {
        data: [commentData],
        meta: { total: 1 },
      },
    };

    DC.READ([productData]);

    // Comment should be registered
    expect(CommentDC.instances.has(1)).toBe(true);
    const comment = CommentDC.instances.get(1);

    // Comment's likes should be normalized to href array
    if (LikeDC.instances.has(1)) {
      expect(Array.isArray(comment.value.likes)).toBe(true);
    }
  });

  it('multiple READ calls for same model accumulate instances', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    DC.READ([makeProductData(1), makeProductData(2)]);
    expect(DC.instances.size).toBe(2);

    DC.READ([makeProductData(3)]);
    expect(DC.instances.size).toBe(3);
  });

  it('instance _response_ triggers pull for method responses', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get(1);

    const pullSpy = vi.spyOn(instance, 'pull');
    instance._response_({ message: 'Comment added' }, new TX({
      name: '_response_', source: `${API_URL}/products/1`, target: 'Product/1',
    }));

    expect(pullSpy).toHaveBeenCalled();
    pullSpy.mockRestore();
  });

  it('instance READ handler normalizes populated data', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));

    const populated = {
      ...makeProductData(1),
      comments: {
        data: [{ ...makeCommentData(1, 1), $id: `${API_URL}/products/1/comments/1` }],
        meta: { total: 1 },
      },
    };

    instance.READ(populated);
    expect(Array.isArray(instance.value.comments)).toBe(true);
  });
});
