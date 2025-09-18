import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X, Film, Sparkles, Zap, Star } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { searchMovies } from '../utils/api.js';
import type { Movie } from '../types/index.js';

interface SearchComponentProps {
  onMovieSelect: (movie: Movie) => void;
  placeholder?: string;
  className?: string;
}

const SearchComponent: React.FC<SearchComponentProps> = ({
  onMovieSelect,
  placeholder = "Search for movies...",
  className = '',
}) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const { data: searchResults = [], isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => searchMovies({ q: query, limit: 8 }),
    enabled: query.length >= 2,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (query.length >= 2) {
      setIsOpen(true);
      setSelectedIndex(-1);
    } else {
      setIsOpen(false);
    }
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        resultsRef.current &&
        !resultsRef.current.contains(event.target as Node) &&
        !inputRef.current?.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || searchResults.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev < searchResults.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev > 0 ? prev - 1 : searchResults.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && searchResults[selectedIndex]) {
          handleMovieSelect(searchResults[selectedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setSelectedIndex(-1);
        inputRef.current?.blur();
        break;
    }
  };

  const handleMovieSelect = (movie: Movie) => {
    onMovieSelect(movie);
    setQuery('');
    setIsOpen(false);
    setSelectedIndex(-1);
    inputRef.current?.blur();
  };

  const clearSearch = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setQuery('');
    setIsOpen(false);
    setSelectedIndex(-1);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleInputFocus = () => {
    setIsFocused(true);
    if (query.length >= 2) setIsOpen(true);
  };

  const handleInputBlur = () => {
    // Delay blur to allow for dropdown clicks
    setTimeout(() => {
      if (!resultsRef.current?.contains(document.activeElement)) {
        setIsFocused(false);
      }
    }, 150);
  };

  const cleanTitle = (title: string, year?: number) => {
    if (!title) return 'Untitled';
    let cleanTitle = title.replace(/\s*\(\d{4}\)$/, '').trim();
    if (year) {
      return `${cleanTitle} (${year})`;
    }
    return cleanTitle;
  };

  return (
    <div className={`relative ${className}`}>
      {/* Search Input Container */}
      <motion.div
        className="relative"
        animate={{
          scale: isFocused ? 1.02 : 1,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        {/* Background glow effect */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isFocused ? 1 : 0 }}
          className="absolute inset-0 rounded-3xl bg-gradient-to-r from-purple-400/20 to-blue-400/20 blur-2xl -z-10"
        />

        {/* Main input container */}
        <div className="relative glass-strong rounded-3xl overflow-hidden">
          {/* Search icon */}
          <div className="absolute left-6 top-1/2 transform -translate-y-1/2 z-20 pointer-events-none">
            <motion.div
              animate={{
                scale: isFocused ? 1.1 : 1,
                rotate: isFocused ? 180 : 0,
              }}
              transition={{ duration: 0.3 }}
            >
              <Search className="w-6 h-6 text-purple-400" />
            </motion.div>
          </div>
          
          {/* Input field */}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            placeholder={placeholder}
            className="w-full pl-16 pr-20 py-6 bg-transparent text-white placeholder-gray-300 focus:outline-none text-lg font-medium relative z-10 cursor-text"
            style={{ pointerEvents: 'auto' }}
            autoComplete="off"
            spellCheck="false"
          />
          
          {/* Right side controls */}
          <div className="absolute right-6 top-1/2 transform -translate-y-1/2 flex items-center gap-3 z-20">
            {/* Loading indicator */}
            {isLoading && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
                className="relative pointer-events-none"
              >
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  className="w-6 h-6 border-2 border-purple-400 border-t-transparent rounded-full"
                />
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="absolute inset-0 border-2 border-purple-400/30 rounded-full"
                />
              </motion.div>
            )}
            
            {/* Clear button */}
            {query && !isLoading && (
              <motion.button
                initial={{ scale: 0, rotate: -90 }}
                animate={{ scale: 1, rotate: 0 }}
                exit={{ scale: 0, rotate: -90 }}
                onClick={clearSearch}
                onMouseDown={(e) => e.preventDefault()}
                className="w-8 h-8 glass rounded-full flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/20 transition-all duration-200 z-30"
                type="button"
              >
                <X className="w-5 h-5" />
              </motion.button>
            )}

            {/* AI indicator */}
            {isFocused && (
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="flex items-center gap-1 text-xs text-purple-400 font-medium pointer-events-none"
              >
                <Zap className="w-4 h-4" />
                AI
              </motion.div>
            )}
          </div>

          {/* Animated border */}
          <motion.div
            className="absolute inset-0 rounded-3xl border-2 border-transparent pointer-events-none"
            animate={{
              borderColor: isFocused ? 'rgba(147, 51, 234, 0.5)' : 'rgba(255, 255, 255, 0.1)',
            }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </motion.div>

      {/* Search Results Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={resultsRef}
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            transition={{ 
              type: "spring",
              stiffness: 400,
              damping: 25
            }}
            className="absolute top-full left-0 right-0 mt-4 glass-strong rounded-3xl shadow-2xl z-50 max-h-96 overflow-hidden"
          >
            {/* Loading state */}
            {isLoading && (
              <div className="p-8 text-center">
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center gap-4"
                >
                  <div className="relative">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      className="w-8 h-8 border-3 border-purple-400 border-t-transparent rounded-full"
                    />
                    <motion.div
                      animate={{ scale: [1, 1.5, 1], opacity: [1, 0.3, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                      className="absolute inset-0 border-3 border-purple-400/30 rounded-full"
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-lg font-semibold text-white">Searching the universe...</p>
                    <p className="text-sm text-gray-400">Finding the perfect matches for you</p>
                  </div>
                </motion.div>
              </div>
            )}

            {/* Empty state */}
            {!isLoading && searchResults.length === 0 && query.length >= 2 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-8 text-center"
              >
                <motion.div
                  animate={{ 
                    y: [0, -10, 0],
                    rotate: [0, 5, -5, 0] 
                  }}
                  transition={{ 
                    duration: 4,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                >
                  <Film className="w-16 h-16 mx-auto mb-4 text-gray-500" />
                </motion.div>
                <div className="space-y-2">
                  <p className="text-lg font-semibold text-white">
                    No movies found for "<span className="text-purple-400">{query}</span>"
                  </p>
                  <p className="text-sm text-gray-400">
                    Try a different search term or browse our collection
                  </p>
                </div>
              </motion.div>
            )}

            {/* Results list */}
            {!isLoading && searchResults.length > 0 && (
              <div className="py-3 max-h-96 overflow-y-auto">
                {searchResults.map((movie: Movie, index: number) => (
                  <motion.button
                    key={movie.movie_id}
                    onClick={() => handleMovieSelect(movie)}
                    onMouseDown={(e) => e.preventDefault()}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ 
                      delay: index * 0.05,
                      type: "spring",
                      stiffness: 300
                    }}
                    className={`w-full px-6 py-4 text-left hover:bg-white/10 transition-all duration-300 
                               flex items-center gap-4 group relative overflow-hidden ${
                                 selectedIndex === index 
                                   ? 'bg-purple-500/20 border-r-4 border-purple-400' 
                                   : ''
                               }`}
                    type="button"
                  >
                    {/* Hover effect background */}
                    <motion.div
                      initial={{ x: '-100%' }}
                      animate={{ x: selectedIndex === index ? '0%' : '-100%' }}
                      className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-transparent pointer-events-none"
                    />

                    {/* Movie poster */}
                    <div className="relative flex-shrink-0 w-16 h-20 rounded-xl overflow-hidden glass">
                      {movie.poster_path ? (
                        <img
                          src={movie.poster_path}
                          alt={`${movie.title} poster`}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-500">
                          <Film className="w-8 h-8" />
                        </div>
                      )}
                      
                      {/* Overlay with rating */}
                      <div className="absolute top-1 right-1 glass px-1 py-0.5 rounded text-xs flex items-center gap-1">
                        <Star className="w-3 h-3 text-yellow-400 fill-current" />
                        <span className="text-white text-xs">
                          {(Math.random() * 2 + 3).toFixed(1)}
                        </span>
                      </div>
                    </div>
                    
                    {/* Movie details */}
                    <div className="flex-grow min-w-0 relative z-10">
                      <div className="font-semibold text-white text-lg truncate group-hover:text-purple-300 transition-colors">
                        {cleanTitle(movie.title, movie.year)}
                      </div>
                      
                      {movie.genres && movie.genres.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {movie.genres.slice(0, 3).map((genre: string) => (
                            <span
                              key={genre}
                              className="text-xs px-2 py-1 glass text-gray-300 rounded-lg font-medium"
                            >
                              {genre}
                            </span>
                          ))}
                          {movie.genres.length > 3 && (
                            <span className="text-xs px-2 py-1 glass text-gray-400 rounded-lg">
                              +{movie.genres.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                      
                      {movie.overview && (
                        <p className="text-sm text-gray-400 mt-2 line-clamp-2 leading-relaxed">
                          {movie.overview}
                        </p>
                      )}
                    </div>

                    {/* Action indicator */}
                    <div className="flex-shrink-0 relative z-10">
                      <motion.div
                        initial={{ opacity: 0, scale: 0 }}
                        animate={{ 
                          opacity: selectedIndex === index ? 1 : 0,
                          scale: selectedIndex === index ? 1 : 0
                        }}
                        className="w-8 h-8 glass rounded-full flex items-center justify-center"
                      >
                        <Sparkles className="w-4 h-4 text-purple-400" />
                      </motion.div>
                    </div>

                    {/* Subtle shine effect on hover */}
                    <motion.div
                      initial={{ x: '-100%', opacity: 0 }}
                      animate={{ 
                        x: selectedIndex === index ? '100%' : '-100%',
                        opacity: selectedIndex === index ? [0, 0.5, 0] : 0
                      }}
                      transition={{ duration: 0.6 }}
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent skew-x-12 pointer-events-none"
                    />
                  </motion.button>
                ))}
              </div>
            )}

            {/* Footer with search tips */}
            {searchResults.length > 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-6 py-3 border-t border-white/10 glass"
              >
                <p className="text-xs text-gray-400 text-center">
                  Use ↑↓ to navigate • Press Enter to select • Esc to close
                </p>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SearchComponent;