import base from '../../tests/frontend/vitest.config.js';
import { fileURLToPath } from 'node:url';

export default {
  ...base,
  root: fileURLToPath(new URL('../../tests/frontend/', import.meta.url)),
  test: {
    ...base.test,
    include: [fileURLToPath(new URL('./t02e-native-create.test.js', import.meta.url))],
  },
};
