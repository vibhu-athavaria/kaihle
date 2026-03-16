import { getMasteryStyle, scoreToPercent } from "../mastery";

describe("getMasteryStyle", () => {
  test("score 0.85 → Strong + brand-green classes", () => {
    const s = getMasteryStyle(0.85);
    expect(s.label).toBe("Strong");
    expect(s.dotClass).toBe("bg-brand-green");
    expect(s.textClass).toBe("text-brand-green");
  });
  test("score 0.7 → Developing (boundary — not > 0.7)", () => {
    expect(getMasteryStyle(0.7).label).toBe("Developing");
  });
  test("score 0.71 → Strong (just over boundary)", () => {
    expect(getMasteryStyle(0.71).label).toBe("Strong");
  });
  test("score 0.4 → Developing (lower boundary — >= 0.4)", () => {
    expect(getMasteryStyle(0.4).label).toBe("Developing");
  });
  test("score 0.39 → Needs Work", () => {
    expect(getMasteryStyle(0.39).label).toBe("Needs Work");
    expect(getMasteryStyle(0.39).dotClass).toBe("bg-brand-red");
  });
  test("score null → Not assessed + muted classes", () => {
    const s = getMasteryStyle(null);
    expect(s.label).toBe("Not assessed");
    expect(s.dotClass).toBe("bg-brand-muted");
  });
});

describe("scoreToPercent", () => {
  test('0.72 → "72%"', () => expect(scoreToPercent(0.72)).toBe("72%"));
  test('0.0 → "0%"', () => expect(scoreToPercent(0.0)).toBe("0%"));
  test('1.0 → "100%"', () => expect(scoreToPercent(1.0)).toBe("100%"));
  test('null → "—"', () => expect(scoreToPercent(null)).toBe("—"));
  test('rounds correctly: 0.676 → "68%"', () =>
    expect(scoreToPercent(0.676)).toBe("68%"));
});
