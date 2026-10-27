import { http, HttpResponse } from "msw";
import { configFixture, healthFixture, metricsFixture } from "./fixtures";

const API = "*/api";

export const handlers = [
  http.get(`${API}/health`, () => HttpResponse.json(healthFixture)),
  http.get(`${API}/config`, () => HttpResponse.json(configFixture)),
  http.get(`${API}/metrics`, () => HttpResponse.json(metricsFixture)),
];
