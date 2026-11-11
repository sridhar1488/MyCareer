export const appraisalHeaderLimit = 500;
export const appraisalResponseLimit = 1000;
export const appraisalTextMinimum = 2;

export function isSingleCharacter(value: string) {
  return [...value.trim()].length === 1;
}
