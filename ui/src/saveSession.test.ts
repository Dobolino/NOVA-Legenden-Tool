import assert from "node:assert/strict";
import test from "node:test";
import { SaveSession } from "./saveSession.ts";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("a navigation flush waits for the current write and the newest edit", async () => {
  const writes: { project: string; doc: object }[] = [];
  const first = deferred<string>();
  const second = deferred<string>();
  const session = new SaveSession("A", (project, doc: object) => {
    writes.push({ project, doc });
    return writes.length === 1 ? first.promise : second.promise;
  });
  session.initialize({ text: "saved" });
  const older = { text: "older" };
  session.update(older);
  const autosave = session.flush();
  const newer = { text: "latest" };
  session.update(newer);
  const navigation = session.flush();
  assert.equal(navigation, autosave);
  assert.deepEqual(writes, [{ project: "A", doc: older }]);
  first.resolve("old result");
  await first.promise;
  assert.deepEqual(writes, [{ project: "A", doc: older }, { project: "A", doc: newer }]);
  assert.equal(session.dirty, true);
  second.resolve("new result");
  await navigation;
  assert.equal(session.dirty, false);
  assert.equal(session.result, "new result");
});

test("a failed save retains the document and a later flush retries it", async () => {
  let fail = true;
  const documents: object[] = [];
  const session = new SaveSession("A", async (_project, doc: object) => {
    documents.push(doc);
    if (fail) throw new Error("offline");
    return "saved";
  });
  session.initialize({ text: "original" });
  const doc = { text: "unsaved" };
  session.update(doc);
  await assert.rejects(session.flush(), /offline/);
  assert.equal(session.dirty, true);
  fail = false;
  await session.flush();
  assert.deepEqual(documents, [doc, doc]);
  assert.equal(session.dirty, false);
});

test("separate projects never share a pending document or save target", async () => {
  const writes: { project: string; doc: object }[] = [];
  const save = async (project: string, doc: object) => { writes.push({ project, doc }); };
  const a = new SaveSession("A", save);
  const b = new SaveSession("B", save);
  a.initialize({ text: "A" });
  b.initialize({ text: "B" });
  const edit = { text: "A edited" };
  a.update(edit);
  await Promise.all([a.flush(), b.flush()]);
  assert.deepEqual(writes, [{ project: "A", doc: edit }]);
});
