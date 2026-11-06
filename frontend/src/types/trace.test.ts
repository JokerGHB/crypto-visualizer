import { describe, expect, it } from 'vitest';
import { hexToMatrix, matrixToHex, byteColor, OP_LABELS } from '../types/trace';

describe('十六进制与矩阵互转', () => {
  it('按列主序装填', () => {
    const matrix = hexToMatrix('00112233445566778899aabbccddeeff');
    expect(matrix[0][0]).toBe('00');
    expect(matrix[1][0]).toBe('11');
    expect(matrix[2][0]).toBe('22');
    expect(matrix[3][0]).toBe('33');
    expect(matrix[0][1]).toBe('44');
  });

  it('往返一致', () => {
    const hex = '3243f6a8885a308d313198a2e0370734';
    expect(matrixToHex(hexToMatrix(hex))).toBe(hex);
  });

  it('非法输入抛错', () => {
    expect(() => hexToMatrix('short')).toThrow();
    expect(() => hexToMatrix('zz44f6a8885a308d313198a2e0370734')).toThrow();
  });
});

describe('字节色阶', () => {
  it('返回合法 hsl 字符串', () => {
    expect(byteColor('00')).toMatch(/^hsl\(\d+, 62%, 58%\)$/);
    expect(byteColor('ff')).toMatch(/^hsl\(\d+, 62%, 58%\)$/);
  });

  it('0x00 与 0xff 色相不同', () => {
    expect(byteColor('00')).not.toBe(byteColor('ff'));
  });
});

describe('操作中文名', () => {
  it('七种操作都有对应中文', () => {
    expect(Object.keys(OP_LABELS)).toHaveLength(7);
    expect(OP_LABELS.SubBytes).toBe('字节替代');
    expect(OP_LABELS.MixColumns).toBe('列混合');
    expect(OP_LABELS.InvShiftRows).toBe('逆行移位');
  });
});