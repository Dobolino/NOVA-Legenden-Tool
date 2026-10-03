/** One editor owns one project. Writes are serialized, including explicit flushes. */
export class SaveSession<Doc, Result> {
  readonly projectId: string;
  private readonly save: (projectId: string, document: Doc) => Promise<Result>;
  private document: Doc | null = null;
  private revision = 0;
  private savedRevision = 0;
  private running: Promise<void> | null = null;
  result: Result | null = null;

  constructor(
    projectId: string,
    save: (projectId: string, document: Doc) => Promise<Result>,
  ) {
    this.projectId = projectId;
    this.save = save;
  }

  initialize(document: Doc | null) {
    this.document = document;
    this.revision = this.savedRevision = 0;
  }

  update(document: Doc | null) {
    if (document === this.document) return;
    this.document = document;
    this.revision += 1;
  }

  get dirty() {
    return this.document !== null && this.revision !== this.savedRevision;
  }

  flush(): Promise<void> {
    if (this.running) return this.running;
    this.running = this.drain().finally(() => { this.running = null; });
    return this.running;
  }

  private async drain() {
    while (this.dirty && this.document !== null) {
      const document = this.document;
      const revision = this.revision;
      // Aborting fetch does not cancel a SQLite write. Wait before sending the next one.
      this.result = await this.save(this.projectId, document);
      this.savedRevision = revision;
    }
  }
}
