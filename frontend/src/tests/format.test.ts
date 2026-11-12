import { ageFrom, percent, probability, relativeTime, roundHalfUp, shortId } from "@/lib/format";

describe("formatting", () => {
  it("rounds half up, like the server", () => {
    expect(roundHalfUp(0.125, 2)).toBe(0.13);
    expect(roundHalfUp(2.5)).toBe(3);
    expect(percent(0.0005)).toBe("0.1%");
  });

  it("never rounds a probability to certainty", () => {
    expect(probability(0.99969)).toBe(">99.9%");
    expect(probability(0.9994)).toBe("99.9%");
    expect(probability(0.0001)).toBe("<0.1%");
    expect(probability(0)).toBe("0.0%");
  });

  it("computes ages from birth dates", () => {
    const today = new Date(2026, 10, 12);
    expect(ageFrom("1975-03-15", today)).toBe(51);
    expect(ageFrom("1968-11-13", today)).toBe(57);
    expect(ageFrom("1968-11-12", today)).toBe(58);
  });

  it("describes recent times", () => {
    const now = Date.parse("2026-11-12T12:00:00Z");
    expect(relativeTime("2026-11-12T11:59:40Z", now)).toBe("just now");
    expect(relativeTime("2026-11-12T11:15:00Z", now)).toBe("45 min ago");
    expect(relativeTime("2026-11-12T06:00:00Z", now)).toBe("6 h ago");
    expect(relativeTime("2026-11-10T12:00:00Z", now)).toBe("2 d ago");
  });

  it("shortens UUIDs but not sample IDs", () => {
    expect(shortId("9143dfcb-d77d-4560-8cd6-325721f7d32d")).toBe("9143dfcb");
    expect(shortId("sample-01")).toBe("sample-01");
  });
});
