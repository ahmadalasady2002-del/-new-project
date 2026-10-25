import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  calculateGold,
  formatIQD,
  formatRawInput,
  sanitizeNumber,
  MAKING_TYPES,
} from './gold.js';

test('reference example: 980,000 / 7.35g / 12,000 per gram = 1,528,800', () => {
  const r = calculateGold({
    mithqalPrice: 980000,
    weight: 7.35,
    making: 12000,
    makingType: MAKING_TYPES.PER_GRAM,
  });
  assert.equal(r.gramPrice, 196000);
  assert.equal(r.finalGramPrice, 208000);
  assert.equal(r.totalMaking, 88200);
  assert.equal(Math.round(r.goldValue), 1440600);
  assert.equal(r.finalPrice, 1528800);
  assert.equal(formatIQD(r.finalPrice), '1,528,800');
});

test('fixed making charge is added once to the piece', () => {
  const r = calculateGold({
    mithqalPrice: 980000,
    weight: 5,
    making: 50000,
    makingType: MAKING_TYPES.FIXED,
  });
  assert.equal(r.totalMaking, 50000);
  assert.equal(r.makingPerGram, 10000);
  assert.equal(r.finalPrice, 980000 + 50000);
});

test('zero weight yields no price and is not ready', () => {
  const r = calculateGold({ mithqalPrice: 980000, weight: 0, making: 50000, makingType: MAKING_TYPES.FIXED });
  assert.equal(r.finalPrice, 0);
  assert.equal(r.ready, false);
});

test('sanitizeNumber rejects negatives, letters and extra dots', () => {
  assert.equal(sanitizeNumber('-500'), '500');
  assert.equal(sanitizeNumber('9a8b0,000'), '980000');
  assert.equal(sanitizeNumber('5.6.2', { decimals: 3 }), '5.62');
  assert.equal(sanitizeNumber('5.6234', { decimals: 3 }), '5.623');
  assert.equal(sanitizeNumber('.5', { decimals: 3 }), '0.5');
  assert.equal(sanitizeNumber('007'), '7');
  assert.equal(sanitizeNumber('١٢٫٥', { decimals: 2 }), '12.5');
  assert.equal(sanitizeNumber('12.5'), '12'); // whole-dinar fields ignore fractions
});

test('formatRawInput keeps the decimal part while typing', () => {
  assert.equal(formatRawInput('1528800'), '1,528,800');
  assert.equal(formatRawInput('7.'), '7.');
  assert.equal(formatRawInput('1234.56'), '1,234.56');
});
