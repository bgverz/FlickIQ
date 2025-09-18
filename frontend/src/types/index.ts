export interface Movie {
  movie_id: number;
  title: string;
  year?: number;
  overview?: string;
  poster_path?: string;
  genres?: string[];
}

export interface User {
  user_id: number;
  created_at?: string;
}

export interface Interaction {
  user_id: number;
  movie_id: number;
  rating?: number;
  weight?: number;
  interaction_type: string;
  interacted_at?: string;
}

export interface InteractionsResponse {
  user_id: number;
  count: number;
  items: Interaction[];
}

export interface RecommendationResponse {
  user_id: number;
  items: Movie[];
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}

export interface CreateUserPayload {
  user_id: number;
}

export interface InteractionPayload {
  user_id: number;
  movie_id: number;
  rating?: number;
  weight?: number;
  interaction_type?: string;
}

export interface SearchParams {
  q: string;
  limit?: number;
  include_low_quality?: boolean;
}

export interface BrowseParams {
  limit?: number;
  offset?: number;
  genre?: string;
  year_min?: number;
  year_max?: number;
  include_low_quality?: boolean;
}

export interface TrendingParams {
  days?: number;
  limit?: number;
  include_low_quality?: boolean;
}

export interface LikedMoviesParams {
  limit?: number;
  min_rating?: number;
}

export interface SimilarParams {
  limit?: number;
}

export interface UserProfile {
  display_name: string;
  bio: string;
}