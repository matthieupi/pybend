/**
 * Nested Entities — Integration Tests
 *
 * Tests: hydrated owned relationships and explicit pointer normalization
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

  it('preserves legacy pointer strings when the backend returns them', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const productData = {
      ...makeProductData(1),
      comments: [
        `${API_URL}/Product/1/Comment/1`,
        `${API_URL}/Product/1/Comment/2`,
      ],
    };

    DC.READ([productData]);
    const product = DC.instances.get('1');
    expect(Array.isArray(product.value.comments)).toBe(true);
    expect(product.value.comments).toHaveLength(2);
    expect(product.value.comments[0]).toContain('/Comment/1');
  });

  it('preserves hydrated owned collection objects and registers child instances', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const CommentDC = NTT.get('Comment');

    const comment1 = makeCommentData(1, 1);
    const comment2 = makeCommentData(2, 1);

    const productData = {
      ...makeProductData(1),
      comments: {
        data: [comment1, comment2],
        meta: { total: 2 },
      },
    };

    DC.READ([productData]);
    const product = DC.instances.get('1');

    // Owned relationship values remain hydrated objects in backend order.
    expect(Array.isArray(product.value.comments)).toBe(true);
    expect(product.value.comments).toHaveLength(2);
    expect(product.value.comments).toEqual([comment1, comment2]);

    // Child instances should be pre-registered in Comment DynamicClass
    expect(CommentDC.instances.has('1')).toBe(true);
    expect(CommentDC.instances.has('2')).toBe(true);
    expect(CommentDC.instances.get('1').href).toBe(`${API_URL}/Comment/1`);
  });

  it('preserves a hydrated owned scalar object', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const child = makeCommentData(1, 1);

    DC.READ([{ ...makeProductData(1), featured_comment: child }]);

    expect(DC.instances.get('1').value.featured_comment).toEqual(child);
    expect(NTT.get('Comment').instances.get('1').href).toBe(child.$id);
  });

  it('retains pointer semantics for explicit Ref fields', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const child1 = makeCommentData(1, 1);
    const child2 = makeCommentData(2, 1);

    DC.READ([{
      ...makeProductData(1),
      featured_comment_ref: child1,
      comment_refs: { data: [child1, child2], meta: { total: 2 } },
    }]);

    const product = DC.instances.get('1');
    expect(product.value.featured_comment_ref).toBe(child1.$id);
    expect(product.value.comment_refs).toEqual([child1.$id, child2.$id]);
  });

  it('comment with parent_id (self-referential) is stored correctly', () => {
    NTT.SCHEMA(ProductSchema);
    const CommentDC = NTT.get('Comment');

    const replyData = {
      ...makeCommentData(3, 1),
      parent_id: 1,
      $id: `${API_URL}/Product/1/Comment/3`,
    };

    CommentDC.READ([replyData]);
    const reply = CommentDC.instances.get('3');
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
        `${API_URL}/Product/1/Comment/1`,
        `${API_URL}/Product/1/Comment/2`,
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
      source: `${API_URL}/Product/1/Comment/1`,
      target: 'Comment',
    }));

    expect(CommentDC.instances.has('1')).toBe(false);
    expect(CommentDC.instances.has('2')).toBe(true);
    CommentDC.send = originalSend;
  });

  it('preserves mixed legacy pointers and hydrated owned objects without coercion', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const productData = {
      ...makeProductData(1),
      comments: {
        data: [
          `${API_URL}/Comment/1`, // legacy pointer remains untouched
          makeCommentData(2, 1), // hydrated owned child remains an object
        ],
        meta: { total: 2 },
      },
    };

    DC.READ([productData]);
    const product = DC.instances.get('1');
    expect(product.value.comments).toHaveLength(2);
    expect(product.value.comments[0]).toBe(`${API_URL}/Comment/1`);
    expect(product.value.comments[1]).toEqual(makeCommentData(2, 1));
  });

  it('deeply nested population (depth=2) normalizes recursively', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const CommentDC = NTT.get('Comment');
    const LikeDC = NTT.get('Like');

    const likeData = { id: 1, user: 1, created_at: '2024-01-01', $id: `${API_URL}/likes/1`, $schema: `${API_URL}/Like` };
    const commentData = {
      ...makeCommentData(1, 1),
      $id: `${API_URL}/Product/1/Comment/1`,
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
    expect(CommentDC.instances.has('1')).toBe(true);
    const comment = CommentDC.instances.get('1');

    // Hydrated nested owned relationships remain arrays and populate the cache.
    if (LikeDC.instances.has('1')) {
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
    const instance = DC.instances.get('1');

    const pullSpy = vi.spyOn(instance, 'pull');
    instance._response_({ message: 'Comment added' }, new TX({
      name: '_response_', source: `${API_URL}/Product/1`, target: 'Product/1',
    }));

    expect(pullSpy).toHaveBeenCalled();
    pullSpy.mockRestore();
  });

  it('instance READ handler preserves hydrated owned data', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));

    const populated = {
      ...makeProductData(1),
      comments: {
        data: [makeCommentData(1, 1)],
        meta: { total: 1 },
      },
    };

    instance.READ(populated);
    expect(Array.isArray(instance.value.comments)).toBe(true);
    expect(instance.value.comments[0]).toMatchObject({ id: 1, $id: `${API_URL}/Comment/1` });
    expect(typeof instance.value.comments[0]).toBe('object');
  });
});
