// Evaluation policy composed through DSH's documented tools.guard() seam.
// This does not replace the DSH agent loop, prompts, tools, or model adapter.
import { realpathSync, existsSync } from 'node:fs';
import { resolve, relative, isAbsolute, dirname } from 'node:path';

export const name = 'glossx-evaluation-read-boundary';
export const inject = ['tools'];

function canonical(path) {
  let cursor = resolve(path);
  const tail = [];
  while (!existsSync(cursor)) {
    const parent = dirname(cursor);
    if (parent === cursor) throw new Error('Unresolvable path');
    tail.unshift(cursor.slice(parent.length + (parent.endsWith('\\') || parent.endsWith('/') ? 0 : 1)));
    cursor = parent;
  }
  return resolve(realpathSync.native(cursor), ...tail);
}

export function apply(ctx) {
  const root = canonical(process.cwd());
  ctx.tools.guard((execution) => {
    if (!['read', 'glob', 'grep'].includes(execution.name)) {
      return { reason: 'This local-document evaluation permits only read, glob, and grep.', info: { name: 'EvaluationPolicyError', code: 'EVAL_TOOL_DENIED' } };
    }
    const args = execution.arguments ?? {};
    const requested = execution.name === 'read' ? args.file_path : (args.path ?? '.');
    if (typeof requested !== 'string') return 'A local workspace path is required.';
    try {
      const target = canonical(resolve(root, requested));
      const rel = relative(root, target);
      if (rel === '..' || rel.startsWith('..\\') || rel.startsWith('../') || isAbsolute(rel)) {
        return { reason: 'Only the supplied task workspace may be read. Parent directories, answer keys, and other runs are inaccessible.', info: { name: 'EvaluationPolicyError', code: 'EVAL_PATH_DENIED' } };
      }
    } catch {
      return 'The supplied workspace path could not be resolved.';
    }
    return undefined;
  });
}
