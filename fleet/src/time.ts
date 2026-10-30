export interface Clock {
  now(): Date;
}

export class SystemClock implements Clock {
  now(): Date {
    return new Date();
  }
}

export class FixedClock implements Clock {
  #current: Date;

  constructor(initialIso: string = "2026-10-30T00:00:00.000Z") {
    this.#current = new Date(initialIso);
  }

  now(): Date {
    return new Date(this.#current.getTime());
  }

  advance(ms: number): void {
    this.#current = new Date(this.#current.getTime() + ms);
  }

  set(iso: string): void {
    this.#current = new Date(iso);
  }
}

export function nowIso(clock: Clock): string {
  return clock.now().toISOString();
}
