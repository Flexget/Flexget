export const LOADING_STATUS = 'LOADING_STATUS';
export const ERROR_STATUS = 'ERROR_STATUS';
export const CLOSE_STATUS = 'CLOSE_STATUS';
export const INFO_STATUS = 'INFO_STATUS';

export function clearStatus() {
  return {
    type: CLOSE_STATUS,
  };
}
