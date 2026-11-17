import type { User } from '../api/client';

export function profileCountry({ country, location }: Pick<User, 'country' | 'location'>): string {
  const recordedCountry = country?.trim();
  if (recordedCountry) return recordedCountry;

  const office = location?.trim().toLowerCase();
  return office === 'bangalore' || office === 'bengaluru' ? 'India' : '';
}
