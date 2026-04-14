import type { QuoteStatus } from '../types';
import { apiGet } from './api';

export interface OfferteListItem {
  id: string;
  client: string;
  description: string;
  amount: number;
  status: QuoteStatus;
}

interface OffertesApiItem {
  id?: unknown;
  code?: unknown;
  client?: unknown;
  klant?: unknown;
  klant_naam?: unknown;
  customer_name?: unknown;
  description?: unknown;
  omschrijving?: unknown;
  amount?: unknown;
  bedrag?: unknown;
  status?: unknown;
}

const validStatuses: QuoteStatus[] = ['wordt_voorbereid', 'open', 'akkoord', 'verloren'];

function toStatus(value: unknown): QuoteStatus {
  if (typeof value !== 'string') {
    return 'open';
  }

  const normalized = value.trim().toLowerCase();
  if (validStatuses.includes(normalized as QuoteStatus)) {
    return normalized as QuoteStatus;
  }

  if (normalized === 'in_behandeling' || normalized === 'bezig') {
    return 'wordt_voorbereid';
  }
  if (normalized === 'accepted' || normalized === 'accepted_quote' || normalized === 'geaccepteerd') {
    return 'akkoord';
  }
  if (normalized === 'lost' || normalized === 'afgewezen') {
    return 'verloren';
  }

  return 'open';
}

function toStringValue(value: unknown, fallback: string): string {
  if (typeof value === 'string' && value.trim().length > 0) {
    return value;
  }
  return fallback;
}

function toNumberValue(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function mapApiItemToOfferte(item: OffertesApiItem): OfferteListItem {
  const id = toStringValue(item.id ?? item.code, 'Onbekend');
  const client = toStringValue(item.client ?? item.klant_naam ?? item.klant ?? item.customer_name, 'Onbekende klant');
  const description = toStringValue(item.description ?? item.omschrijving, '-');
  const amount = toNumberValue(item.amount ?? item.bedrag);
  const status = toStatus(item.status);

  return {
    id,
    client,
    description,
    amount,
    status,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function extractList(payload: unknown): OffertesApiItem[] {
  if (Array.isArray(payload)) {
    return payload.filter(isRecord);
  }

  if (isRecord(payload)) {
    const candidates: unknown[] = [payload.items, payload.data, payload.offertes];
    for (const candidate of candidates) {
      if (Array.isArray(candidate)) {
        return candidate.filter(isRecord);
      }
    }
  }

  return [];
}

export async function getOffertes(): Promise<OfferteListItem[]> {
  const payload = await apiGet<unknown>('/offertes');
  const list = extractList(payload);
  return list.map(mapApiItemToOfferte);
}
