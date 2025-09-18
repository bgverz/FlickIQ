import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles, TrendingUp, Shuffle, Sliders, Star, Zap, Film, ChevronLeft, ChevronRight } from 'lucide-react';
import { toast } from 'react-hot-toast';

import SearchComponent from '../components/SearchComponent.js';
import MovieCard from '../components/MovieCard.js';
import { 
  getRecommendations, 
  getTrendingMovies, 
  getAllMovies, 
  getSimilarMovies,
  createInteraction,
  deleteInteraction,
  getLikedMovies
} from '../utils/api.js';
import type { Movie } from '../types/index.js';

interface HomePageProps {
  userId: number;
}

const HomePage: React.FC<HomePageProps> = ({ userId }) => {
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [similarResults, setSimilarResults] = useState<Movie[]>([]);
  const [similarTitle, setSimilarTitle] = useState('');
  const [recommendationLimit, setRecommendationLimit] = useState(12);
  const [browseFilters, setBrowseFilters] = useState({
    genre: '',
    yearFilter: '',
    limit: 24
  });
  const [showBrowse, setShowBrowse] = useState(false);

  const queryClient = useQueryClient();

  // Get user's liked movies
  const { data: likedMovies = [] } = useQuery({
    queryKey: ['likedMovies', userId],
    queryFn: () => getLikedMovies(userId, { limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });

  const likedMovieIds = new Set(likedMovies.map((movie: Movie) => movie.movie_id));

  // Get recommendations
  const { data: recommendationsData, isLoading: isLoadingRecs, refetch: refetchRecommendations } = useQuery({
    queryKey: ['recommendations', userId, recommendationLimit],
    queryFn: () => getRecommendations(userId, recommendationLimit),
    enabled: false,
  });

  // Get trending movies
  const { data: trendingMovies = [], isLoading: isLoadingTrending } = useQuery({
    queryKey: ['trending'],
    queryFn: () => getTrendingMovies({ days: 7, limit: 24 }),
    staleTime: 30 * 60 * 1000,
  });

  // Browse movies
  const { data: browseMovies = [], isLoading: isLoadingBrowse, refetch: refetchBrowse } = useQuery({
    queryKey: ['browseMovies', browseFilters],
    queryFn: () => {
      const params: any = { 
        limit: browseFilters.limit,
        include_low_quality: false 
      };
      
      if (browseFilters.genre) params.genre = browseFilters.genre;
      
      if (browseFilters.yearFilter === '2020+') {
        params.year_min = 2020;
      } else if (browseFilters.yearFilter === '2010-2019') {
        params.year_min = 2010;
        params.year_max = 2019;
      } else if (browseFilters.yearFilter === '2000-2009') {
        params.year_min = 2000;
        params.year_max = 2009;
      } else if (browseFilters.yearFilter === '1990-1999') {
        params.year_min = 1990;
        params.year_max = 1999;
      }
      
      return getAllMovies(params);
    },
    enabled: showBrowse,
  });

  // Mutations
  const likeMutation = useMutation({
    mutationFn: (movieId: number) => 
      createInteraction({ 
        user_id: userId, 
        movie_id: movieId, 
        interaction_type: 'like' 
      }),
    onSuccess: () => {
      toast.success('Added to favorites!');
      queryClient.invalidateQueries({ queryKey: ['likedMovies', userId] });
    },
    onError: () => toast.error('Failed to add to favorites'),
  });

  const similarMutation = useMutation({
    mutationFn: (movieId: number) => getSimilarMovies(movieId, { limit: 24 }),
    onSuccess: (data, movieId) => {
      setSimilarResults(data);
      const movie = selectedMovie || 
        [...(recommendationsData?.items || []), ...trendingMovies, ...browseMovies]
          .find((m: Movie) => m.movie_id === movieId);
      setSimilarTitle(movie?.title || 'Unknown Movie');
      toast.success('Similar movies found!');
    },
    onError: () => toast.error('Failed to get similar movies'),
  });

  const handleMovieSelect = (movie: Movie) => {
    setSelectedMovie(movie);
    setSimilarResults([]);
    setSimilarTitle('');
  };

  const handleLike = (movieId: number) => {
    likeMutation.mutate(movieId);
  };

  const handleSimilar = (movieId: number) => {
    similarMutation.mutate(movieId);
  };

  const handleGetRecommendations = () => {
    refetchRecommendations();
  };

  const clearSearch = () => {
    setSelectedMovie(null);
    setSimilarResults([]);
    setSimilarTitle('');
  };

  const LoadingGrid = ({ count = 12 }: { count?: number }) => (
    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="aspect-[2/3] glass rounded-2xl loading-shimmer" />
      ))}
    </div>
  );

  const MovieGrid = ({ movies, section = "default" }: { movies: Movie[], section?: string }) => (
    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
      {movies.map((movie: Movie) => (
        <MovieCard
          key={`${section}-${movie.movie_id}`}
          movie={movie}
          onLike={handleLike}
          onSimilar={handleSimilar}
          isLiked={likedMovieIds.has(movie.movie_id)}
          className="w-full"
        />
      ))}
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* Enhanced background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-violet-900/20 via-transparent to-transparent" />
        
        {/* Animated mesh gradient */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
          <div className="absolute top-0 -right-4 w-72 h-72 bg-yellow-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-8 left-20 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>
        </div>
      </div>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-6 py-20">
        <div className="max-w-6xl mx-auto text-center space-y-12">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="space-y-8"
          >
            <div className="space-y-6">
              <motion.div
                className="inline-flex items-center gap-2 px-6 py-3 glass rounded-full text-sm font-semibold text-violet-300 border border-violet-500/20"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
              >
                <Zap className="w-4 h-4" />
                AI-Powered Cinema Discovery
              </motion.div>
              
              <h1 className="text-6xl md:text-7xl lg:text-8xl font-black leading-[0.9] tracking-tight">
                <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-indigo-400 bg-clip-text text-transparent">
                  Discover
                </span>
                <br />
                <span className="text-white">Perfect</span>
                <br />
                <span className="bg-gradient-to-r from-pink-400 via-rose-400 to-orange-400 bg-clip-text text-transparent">
                  Movies
                </span>
              </h1>
            </div>
            
            <p className="text-xl md:text-2xl text-slate-300 max-w-4xl mx-auto leading-relaxed font-medium">
              Experience cinema like never before with personalized recommendations powered by advanced machine learning
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="max-w-4xl mx-auto"
          >
            <SearchComponent
              onMovieSelect={handleMovieSelect}
              placeholder="Search thousands of movies..."
              className="mb-10"
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="flex flex-wrap justify-center gap-6"
          >
            <button
              onClick={handleGetRecommendations}
              disabled={isLoadingRecs}
              className="group relative px-10 py-4 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white font-bold rounded-2xl text-lg transition-all duration-300 shadow-xl hover:shadow-violet-500/25 disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <Star className="w-6 h-6" />
                {isLoadingRecs ? 'Creating Magic...' : 'Get My Recommendations'}
              </div>
            </button>
            
            <button
              onClick={() => setShowBrowse(!showBrowse)}
              className="px-10 py-4 glass-button rounded-2xl font-bold text-lg border border-white/20"
            >
              <div className="flex items-center gap-3">
                <Film className="w-6 h-6" />
                Explore Collection
              </div>
            </button>
          </motion.div>
        </div>
      </section>

      {/* Selected Movie Hero */}
      <AnimatePresence>
        {selectedMovie && (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="relative min-h-screen flex items-center mb-24"
          >
            <div 
              className="absolute inset-0 bg-cover bg-center"
              style={{
                backgroundImage: selectedMovie.poster_path 
                  ? `url(${selectedMovie.poster_path})`
                  : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
              }}
            />
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
            <div className="absolute inset-0 bg-gradient-to-r from-black via-black/80 to-transparent" />

            <div className="relative z-10 max-w-7xl mx-auto px-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
                <motion.div
                  initial={{ opacity: 0, x: -50 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="space-y-8"
                >
                  <div className="glass-strong rounded-3xl p-10 space-y-8">
                    <h2 className="text-5xl md:text-6xl font-black text-white leading-tight">
                      {selectedMovie.title}
                    </h2>
                    
                    {selectedMovie.year && (
                      <div className="flex items-center gap-4">
                        <span className="text-3xl text-violet-300 font-bold">{selectedMovie.year}</span>
                        <div className="flex gap-1">
                          {Array.from({ length: 5 }).map((_, i) => (
                            <Star key={i} className="w-6 h-6 text-yellow-400 fill-current" />
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedMovie.genres && selectedMovie.genres.length > 0 && (
                      <div className="flex flex-wrap gap-3">
                        {selectedMovie.genres.map((genre: string) => (
                          <span
                            key={genre}
                            className="px-4 py-2 glass rounded-full text-sm font-semibold text-white border border-white/30"
                          >
                            {genre}
                          </span>
                        ))}
                      </div>
                    )}

                    <p className="text-lg text-slate-200 leading-relaxed">
                      {selectedMovie.overview || 'Experience cinema like never before.'}
                    </p>

                    <div className="flex flex-wrap gap-4">
                      <button
                        onClick={() => handleLike(selectedMovie.movie_id)}
                        disabled={likedMovieIds.has(selectedMovie.movie_id)}
                        className="flex items-center gap-3 px-10 py-4 bg-white text-black font-bold rounded-2xl hover:bg-slate-100 transition-all duration-300 disabled:opacity-50"
                      >
                        <Star className="w-6 h-6" />
                        {likedMovieIds.has(selectedMovie.movie_id) ? 'In Favorites' : 'Add to Favorites'}
                      </button>
                      
                      <button
                        onClick={() => handleSimilar(selectedMovie.movie_id)}
                        className="glass-button px-10 py-4 rounded-2xl font-bold"
                      >
                        <div className="flex items-center gap-3">
                          <Sparkles className="w-6 h-6" />
                          Find Similar
                        </div>
                      </button>
                      
                      <button
                        onClick={clearSearch}
                        className="glass-button px-10 py-4 rounded-2xl font-bold opacity-75 hover:opacity-100"
                      >
                        New Search
                      </button>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="relative hidden lg:block"
                >
                  <div className="relative">
                    <div className="absolute inset-0 bg-gradient-to-t from-violet-500/30 to-purple-500/30 rounded-3xl blur-3xl" />
                    <img
                      src={selectedMovie.poster_path || 'https://placehold.co/400x600?text=No+Poster'}
                      alt={`${selectedMovie.title} poster`}
                      className="relative w-full max-w-md mx-auto rounded-3xl shadow-2xl"
                    />
                  </div>
                </motion.div>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Content Sections */}
      <div className="relative max-w-7xl mx-auto px-6 space-y-20 pb-24">
        {/* Similar Movies */}
        <AnimatePresence>
          {similarResults.length > 0 && (
            <motion.section
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -50 }}
              className="space-y-8"
            >
              <div className="glass-strong rounded-3xl p-10">
                <h2 className="text-4xl font-black text-white flex items-center gap-4 mb-10">
                  <Sparkles className="w-10 h-10 text-violet-400" />
                  Similar to {similarTitle}
                </h2>
                <MovieGrid movies={similarResults} section="similar" />
              </div>
            </motion.section>
          )}
        </AnimatePresence>

        {/* Recommendations */}
        {recommendationsData && (
          <motion.section
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-strong rounded-3xl p-10 space-y-8"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-4xl font-black text-white flex items-center gap-4">
                <Star className="w-10 h-10 text-yellow-400" />
                Made for You
              </h2>
              <select
                value={recommendationLimit}
                onChange={(e) => setRecommendationLimit(Number(e.target.value))}
                className="glass px-6 py-3 rounded-xl text-white font-semibold focus-glass"
              >
                <option value={12}>12 movies</option>
                <option value={24}>24 movies</option>
                <option value={36}>36 movies</option>
              </select>
            </div>
            <MovieGrid movies={recommendationsData.items} section="recommendations" />
          </motion.section>
        )}

        {/* Trending */}
        <motion.section
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-3xl p-10 space-y-8"
        >
          <h2 className="text-4xl font-black text-white flex items-center gap-4">
            <TrendingUp className="w-10 h-10 text-emerald-400" />
            Trending Now
          </h2>
          
          {isLoadingTrending ? (
            <LoadingGrid count={24} />
          ) : (
            <MovieGrid movies={trendingMovies} section="trending" />
          )}
        </motion.section>

        {/* Browse Section */}
        <motion.section
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-strong rounded-3xl p-10 space-y-8"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-4xl font-black text-white flex items-center gap-4">
              <Shuffle className="w-10 h-10 text-purple-400" />
              Explore Collection
            </h2>
            
            <button
              onClick={() => setShowBrowse(!showBrowse)}
              className="glass-button px-8 py-3 rounded-xl font-bold flex items-center gap-3"
            >
              <Sliders className="w-5 h-5" />
              {showBrowse ? 'Hide Filters' : 'Show Filters'}
            </button>
          </div>

          <AnimatePresence>
            {showBrowse && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="glass rounded-2xl p-8"
              >
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-3">
                      Movies Count
                    </label>
                    <select
                      value={browseFilters.limit}
                      onChange={(e) => setBrowseFilters(prev => ({ ...prev, limit: Number(e.target.value) }))}
                      className="w-full glass px-4 py-3 rounded-xl text-white font-semibold focus-glass"
                    >
                      <option value={12}>12 movies</option>
                      <option value={24}>24 movies</option>
                      <option value={48}>48 movies</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-3">
                      Genre
                    </label>
                    <select
                      value={browseFilters.genre}
                      onChange={(e) => setBrowseFilters(prev => ({ ...prev, genre: e.target.value }))}
                      className="w-full glass px-4 py-3 rounded-xl text-white font-semibold focus-glass"
                    >
                      <option value="">All genres</option>
                      <option value="Action">Action</option>
                      <option value="Comedy">Comedy</option>
                      <option value="Drama">Drama</option>
                      <option value="Horror">Horror</option>
                      <option value="Sci-Fi">Sci-Fi</option>
                      <option value="Thriller">Thriller</option>
                      <option value="Romance">Romance</option>
                      <option value="Adventure">Adventure</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-3">
                      Era
                    </label>
                    <select
                      value={browseFilters.yearFilter}
                      onChange={(e) => setBrowseFilters(prev => ({ ...prev, yearFilter: e.target.value }))}
                      className="w-full glass px-4 py-3 rounded-xl text-white font-semibold focus-glass"
                    >
                      <option value="">All years</option>
                      <option value="2020+">2020+</option>
                      <option value="2010-2019">2010-2019</option>
                      <option value="2000-2009">2000-2009</option>
                      <option value="1990-1999">1990-1999</option>
                    </select>
                  </div>
                  
                  <div className="flex items-end">
                    <button
                      onClick={() => {
                        setShowBrowse(true);
                        refetchBrowse();
                      }}
                      disabled={isLoadingBrowse}
                      className="w-full px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold rounded-xl transition-all duration-300 disabled:opacity-50"
                    >
                      {isLoadingBrowse ? 'Loading...' : 'Explore'}
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {browseMovies.length > 0 && (
            <MovieGrid movies={browseMovies} section="browse" />
          )}
        </motion.section>
      </div>
    </div>
  );
};

export default HomePage;