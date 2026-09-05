/**
 * Execution API service (Workstream C: Booking, Re-planning, Disruption Monitoring, Travel Pass).
 */

import { request } from './client';
import type { PlanRequest, PlanResponse } from '../../types/api';

export interface BookingHoldResponse {
  prepared: boolean;
  reference: string;
  status: string;
  route_id: string;
  traveler_name: string;
  seats: number;
  total_fare_lkr: number;
  currency: string;
  expires_in_minutes: number;
  created_at: string;
  expires_at: string;
  data_source: string;
  safety_invariant: string;
}

export interface TravelPassData {
  pass_id: string;
  booking_reference: string;
  status: string;
  traveler_name: string;
  seats: number;
  seat_class: string;
  total_fare_lkr: number;
  currency: string;
  origin: string;
  destination: string;
  departure_time?: string;
  arrival_time?: string;
  duration_min?: number;
  route_id: string;
  summary: string;
  legs: any[];
  qr_code_svg: string;
  offline_instructions: string;
  is_offline_ready: boolean;
  generated_at: string;
  expires_at: string;
}

export function replanRoute(payload: {
  request: PlanRequest;
  previous_recommendation_id?: string;
  disruption_notice?: string;
}): Promise<PlanResponse> {
  return request<PlanResponse>('/api/route/replan', {
    method: 'POST',
    body: payload,
  });
}

export function prepareBookingHold(payload: {
  route_id: string;
  traveler_name?: string;
  seats?: number;
  total_fare_lkr?: number;
  seat_class?: string;
}): Promise<BookingHoldResponse> {
  return request<BookingHoldResponse>('/api/route/hold', {
    method: 'POST',
    body: payload,
  });
}

export function getTravelPass(payload: {
  plan: PlanResponse;
  booking_reference?: string;
  traveler_name?: string;
  seats?: number;
  seat_class?: string;
}): Promise<TravelPassData> {
  return request<TravelPassData>('/api/route/travel-pass', {
    method: 'POST',
    body: payload,
  });
}

export function injectDisruption(payload?: {
  trip_id?: string;
  delay_minutes?: number;
  delay_risk?: string;
  alert_header?: string;
}): Promise<any> {
  return request<any>('/api/route/disruption/inject', {
    method: 'POST',
    body: payload || {
      trip_id: 'trip_train_mainline_1005',
      delay_minutes: 55.0,
      delay_risk: 'high',
    },
  });
}

export function restoreDisruption(): Promise<any> {
  return request<any>('/api/route/disruption/restore', {
    method: 'POST',
    body: {},
  });
}

export function getDisruptionStatus(): Promise<{ active_disruptions: any[]; disrupted_count: number }> {
  return request<{ active_disruptions: any[]; disrupted_count: number }>('/api/route/disruption/status', {
    method: 'GET',
  });
}
