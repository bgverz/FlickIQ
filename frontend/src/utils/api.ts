import axios, { AxiosError } from 'axios';
import type {
  Movie,
  User,
  InteractionsResponse,
  RecommendationResponse,
  CreateUserPayload,
  InteractionPayload,
  SearchParams,
  BrowseParams,
  TrendingParams,
  LikedMoviesParams,
  SimilarParams,
} from '../types/index.js';

const API_BASE = import.meta.env.PROD 
  ? (import.meta.env.VITE_API_BASE || 'http://localhost:8000')
  : '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const healthCheck = async () => {
  const response = await api.get('/healthz');
  return response.data;
};

export const createUser = async (payload: CreateUserPayload): Promise<{ ok: boolean; user_id: number }> => {
  const response = await api.post('/users', payload);
  return response.data;
};

export const createInteraction = async (payload: InteractionPayload) => {
  const response = await api.post('/interactions', payload);
  return response.data;
};

export const getInteractions = async (userId: number, limit = 50, offset = 0): Promise<InteractionsResponse> => {
  const response = await api.get(`/interactions/${userId}`, {
    params: { limit, offset }
  });
  return response.data;
};

export const deleteInteraction = async (userId: number, movieId: number) => {
  const response = await api.delete(`/interactions/${userId}/${movieId}`);
  return response.data;
};

export const getLikedMovies = async (userId: number, params: LikedMoviesParams = {}): Promise<Movie[]> => {
  const response = await api.get(`/users/${userId}/liked`, { params });
  return response.data;
};

export const searchMovies = async (params: SearchParams): Promise<Movie[]> => {
  const response = await api.get('/movies/search', { params });
  return response.data;
};

export const getAllMovies = async (params: BrowseParams = {}): Promise<Movie[]> => {
  const response = await api.get('/movies', { params });
  return response.data;
};

export const getSimilarMovies = async (movieId: number, params: SimilarParams = {}): Promise<Movie[]> => {
  const response = await api.get(`/similar/${movieId}`, { params });
  return response.data;
};

export const getRecommendations = async (userId: number, limit = 10): Promise<RecommendationResponse> => {
  const response = await api.get(`/recommendations/${userId}`, {
    params: { limit }
  });
  return response.data;
};

export const getTrendingMovies = async (params: TrendingParams = {}): Promise<Movie[]> => {
  const response = await api.get('/trending', { params });
  return response.data;
};

export default api;