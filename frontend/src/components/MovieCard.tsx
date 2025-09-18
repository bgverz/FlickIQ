import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Heart, Target, Trash2, Play, Plus, Check, Info, Star } from 'lucide-react';
import type { Movie } from '../types/index.js';

interface MovieCardProps {
  movie: Movie;
  onLike?: (movieId: number) => void;
  onUnlike?: (movieId: number) => void;
  onSimilar?: (movieId: number) => void;
  showLike?: boolean;
  showUnlike?: boolean;
  showSimilar?: boolean;
  isLiked?: boolean;
  className?: string;
}

const MovieCard: React.FC<MovieCardProps> = ({
  movie,
  onLike,
  onUnlike,
  onSimilar,
  showLike = true,
  showUnlike = false,
  showSimilar = true,
  isLiked = false,
  className = '',
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleLike = () => {
    if (onLike && movie.movie_id) {
      onLike(movie.movie_id);
    }
  };

  const handleUnlike = () => {
    if (onUnlike && movie.movie_id) {
      onUnlike(movie.movie_id);
    }
  };

  const handleSimilar = () => {
    if (onSimilar && movie.movie_id) {
      onSimilar(movie.movie_id);
    }
  };

  const cleanTitle = (title: string, year?: number) => {
    if (!title) return 'Untitled';
    
    // Remove year from title if it exists
    let cleanTitle = title.replace(/\s*\(\d{4}\)$/, '').trim();
    
    // Add year back if provided
    if (year) {
      return `${cleanTitle} (${year})`;
    }
    
    return cleanTitle;
  };

  const displayTitle = cleanTitle(movie.title, movie.year);
  const posterUrl = movie.poster_path || 'https://placehold.co/400x600?text=No+Poster';
  const overview = movie.overview || 'No overview available.';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -12, scale: 1.02 }}
      transition={{ 
        duration: 0.4,
        type: "spring",
        stiffness: 300,
        damping: 20
      }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className={`group relative card-hover cursor-pointer ${className}`}
    >
      {/* Main Card Container */}
      <div className="relative glass rounded-3xl overflow-hidden h-full">
        {/* Poster Container */}
        <div className="relative aspect-[2/3] overflow-hidden">
          <motion.img
            src={posterUrl}
            alt={`${movie.title} poster`}
            className="w-full h-full object-cover"
            loading="lazy"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.6 }}
          />
          
          {/* Gradient overlays */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: isHovered ? 1 : 0 }}
            className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent"
          />
          
          {/* Like indicator */}
          {isLiked && (
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              className="absolute top-4 right-4 w-10 h-10 bg-gradient-to-r from-red-500 to-pink-500 rounded-full flex items-center justify-center shadow-lg backdrop-blur-sm"
            >
              <Heart className="w-5 h-5 text-white fill-current" />
            </motion.div>
          )}

          {/* Rating overlay */}
          <div className="absolute top-4 left-4">
            <div className="glass px-3 py-1 rounded-full flex items-center gap-1">
              <Star className="w-4 h-4 text-yellow-400 fill-current" />
              <span className="text-white text-sm font-semibold">
                {(Math.random() * 2 + 3).toFixed(1)}
              </span>
            </div>
          </div>

          {/* Interactive overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: isHovered ? 1 : 0 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="flex gap-3">
              {showLike && (
                <motion.button
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ 
                    scale: isHovered ? 1 : 0,
                    rotate: isHovered ? 0 : -180
                  }}
                  transition={{ delay: 0.1, type: "spring", stiffness: 400 }}
                  onClick={handleLike}
                  disabled={isLiked}
                  className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 backdrop-blur-md ${
                    isLiked
                      ? 'bg-red-500/80 text-white cursor-not-allowed'
                      : 'bg-white/90 hover:bg-white text-black hover:scale-110 shadow-lg'
                  }`}
                >
                  {isLiked ? <Check className="w-5 h-5" /> : <Plus className="w-5 h-5" />}
                </motion.button>
              )}

              {showUnlike && (
                <motion.button
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ 
                    scale: isHovered ? 1 : 0,
                    rotate: isHovered ? 0 : -180
                  }}
                  transition={{ delay: 0.15, type: "spring", stiffness: 400 }}
                  onClick={handleUnlike}
                  className="w-12 h-12 bg-red-500/90 hover:bg-red-500 text-white rounded-full flex items-center justify-center hover:scale-110 transition-all duration-200 backdrop-blur-md shadow-lg"
                >
                  <Trash2 className="w-5 h-5" />
                </motion.button>
              )}

              {showSimilar && (
                <motion.button
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ 
                    scale: isHovered ? 1 : 0,
                    rotate: isHovered ? 0 : -180
                  }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 400 }}
                  onClick={handleSimilar}
                  className="w-12 h-12 bg-purple-500/90 hover:bg-purple-500 text-white rounded-full flex items-center justify-center hover:scale-110 transition-all duration-200 backdrop-blur-md shadow-lg"
                >
                  <Info className="w-5 h-5" />
                </motion.button>
              )}
            </div>
          </motion.div>
        </div>

        {/* Content Section */}
        <motion.div
          className="p-4 space-y-3"
          animate={{
            height: isHovered ? 'auto' : 'auto'
          }}
        >
          <h3 className="font-bold text-white text-sm leading-tight line-clamp-2 group-hover:text-purple-300 transition-colors duration-300">
            {displayTitle}
          </h3>

          {movie.genres && movie.genres.length > 0 && (
            <motion.div
              initial={{ opacity: 0.8 }}
              animate={{ opacity: isHovered ? 1 : 0.8 }}
              className="flex flex-wrap gap-1"
            >
              {movie.genres.slice(0, 2).map((genre: string) => (
                <span
                  key={genre}
                  className="text-xs px-2 py-1 glass text-gray-300 rounded-lg font-medium"
                >
                  {genre}
                </span>
              ))}
              {movie.genres.length > 2 && (
                <span className="text-xs px-2 py-1 glass text-gray-400 rounded-lg">
                  +{movie.genres.length - 2}
                </span>
              )}
            </motion.div>
          )}

          <motion.p
            initial={{ height: '3rem' }}
            animate={{ height: isHovered ? 'auto' : '3rem' }}
            className="text-gray-400 text-xs leading-relaxed overflow-hidden"
          >
            {overview}
          </motion.p>

          {/* Year and additional info */}
          {movie.year && (
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{movie.year}</span>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                <span>Available</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Glow effect on hover */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isHovered ? 1 : 0 }}
          className="absolute inset-0 rounded-3xl"
          style={{
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1))',
            filter: 'blur(20px)',
            zIndex: -1,
          }}
        />
      </div>

      {/* Enhanced shadow on hover */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: isHovered ? 1 : 0 }}
        className="absolute inset-0 rounded-3xl -z-10"
        style={{
          background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2))',
          filter: 'blur(30px)',
          transform: 'translateY(10px) scale(1.05)',
        }}
      />
    </motion.div>
  );
};

export default MovieCard;