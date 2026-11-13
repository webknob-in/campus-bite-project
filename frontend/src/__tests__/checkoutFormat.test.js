import { describe, expect, it } from "vitest";

import { buildOrderPayload, validateCardNumber, validateCvv, validateExpiry } from "../utils/checkoutFormat";

// Requirements 11.12, 49.3: card validation rules.

const NOW = new Date(2026, 5, 15); // June 2026

describe("validateCardNumber", () => {
  it("accepts 16 digits, ignoring spaces", () => {
    expect(validateCardNumber("4111 1111 1111 1111")).toBeUndefined();
    expect(validateCardNumber("4111111111111111")).toBeUndefined();
  });
  it("rejects wrong length, letters and empty", () => {
    expect(validateCardNumber("4111 1111 1111 111")).toBeTruthy();
    expect(validateCardNumber("4111 1111 1111 11111")).toBeTruthy();
    expect(validateCardNumber("4111 1111 1111 111a")).toBeTruthy();
    expect(validateCardNumber("")).toBeTruthy();
  });
});

describe("validateExpiry", () => {
  it("accepts the current month and later", () => {
    expect(validateExpiry("06/26", NOW)).toBeUndefined();
    expect(validateExpiry("01/27", NOW)).toBeUndefined();
  });
  it("rejects past months, bad months and bad formats", () => {
    expect(validateExpiry("05/26", NOW)).toBeTruthy();
    expect(validateExpiry("12/25", NOW)).toBeTruthy();
    expect(validateExpiry("13/30", NOW)).toBeTruthy();
    expect(validateExpiry("00/30", NOW)).toBeTruthy();
    expect(validateExpiry("0630", NOW)).toBeTruthy();
    expect(validateExpiry("", NOW)).toBeTruthy();
  });
});

describe("validateCvv", () => {
  it("accepts exactly 3 digits", () => {
    expect(validateCvv("123")).toBeUndefined();
  });
  it("rejects other lengths and non-digits", () => {
    expect(validateCvv("12")).toBeTruthy();
    expect(validateCvv("1234")).toBeTruthy();
    expect(validateCvv("12a")).toBeTruthy();
    expect(validateCvv("")).toBeTruthy();
  });
});

describe("buildOrderPayload", () => {
  it("maps cart lines and strips card number spaces", () => {
    const payload = buildOrderPayload([{ id: 3, name: "Dosa", price: "40.00", quantity: 2 }], {
      address: " 12 Main Road ",
      phone: "9876543210",
      cardHolder: "Asha",
      cardNumber: "4111 1111 1111 1111",
      expiry: "12/40",
      cvv: "123",
    });
    expect(payload.items).toEqual([{ menu_item_id: 3, quantity: 2 }]);
    expect(payload.delivery_address).toBe("12 Main Road");
    expect(payload.payment.card_number).toBe("4111111111111111");
  });
});
