import { fa } from "./fa";

export * from "./format";
export * from "./places";

// The one copy tree. Reading `t.some.key` is type-checked, so a missing key fails `tsc`.
export const t = fa;
