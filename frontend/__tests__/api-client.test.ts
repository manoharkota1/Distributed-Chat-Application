/**
 * Basic tests for the API client module.
 */

import { setAccessToken, getAccessToken } from '../src/lib/api/client';

describe('API Client', () => {
  it('should store and retrieve access token', () => {
    setAccessToken('test-token-123');
    expect(getAccessToken()).toBe('test-token-123');
  });

  it('should clear access token', () => {
    setAccessToken('test-token');
    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
  });
});
