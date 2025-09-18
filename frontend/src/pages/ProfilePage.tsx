import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { User, Heart, BarChart3, Download, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';

import MovieCard from '../components/MovieCard';
import { getLikedMovies, deleteInteraction, getSimilarMovies } from '../utils/api';
import type { Movie, UserProfile } from '../types';

interface ProfilePageProps {
  userId: number;
  profile: UserProfile;
  onProfileUpdate: (profile: UserProfile) => void;
}

const ProfilePage: React.FC<ProfilePageProps> = ({
  userId,
  profile,
  onProfileUpdate,
}) => {
  const [editMode, setEditMode] = useState(false);
  const [tempProfile, setTempProfile] = useState(profile);
  const [similarResults, setSimilarResults] = useState<Movie[]>([]);
  const [similarTitle, setSimilarTitle] = useState('');

  const queryClient = useQueryClient();

  const { data: likedMovies = [], isLoading } = useQuery({
    queryKey: ['likedMovies', userId],
    queryFn: () => getLikedMovies(userId, { limit: 500 }),
    staleTime: 5 * 60 * 1000,
  });

  const unlikeMutation = useMutation({
    mutationFn: (movieId: number) => deleteInteraction(userId, movieId),
    onSuccess: () => {
      toast.success('Movie removed from likes!');
      queryClient.invalidateQueries({ queryKey: ['likedMovies', userId] });
    },
    onError: (error) => {
      toast.error('Failed to unlike movie');
      console.error('Unlike error:', error);
    },
  });

  const similarMutation = useMutation({
    mutationFn: (movieId: number) => getSimilarMovies(movieId, { limit: 12 }),
    onSuccess: (data, movieId) => {
      setSimilarResults(data);
      const movie = likedMovies.find(m => m.movie_id === movieId);
      setSimilarTitle(movie?.title || 'Unknown Movie');
      toast.success('Similar movies found!');
    },
    onError: (error) => {
      toast.error('Failed to get similar movies');
      console.error('Similar error:', error);
    },
  });

  // Genre statistics
  const genreStats = useMemo(() => {
    const genreCounts: Record<string, number> = {};
    
    likedMovies.forEach(movie => {
      if (movie.genres) {
        movie.genres.forEach(genre => {
          genreCounts[genre] = (genreCounts[genre] || 0) + 1;
        });
      }
    });

    return Object.entries(genreCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8);
  }, [likedMovies]);

  // Year distribution
  const yearStats = useMemo(() => {
    const decades: Record<string, number> = {};
    
    likedMovies.forEach(movie => {
      if (movie.year) {
        const decade = `${Math.floor(movie.year / 10) * 10}s`;
        decades[decade] = (decades[decade] || 0) + 1;
      }
    });

    return Object.entries(decades)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 6);
  }, [likedMovies]);

  const handleProfileSave = () => {
    onProfileUpdate(tempProfile);
    setEditMode(false);
    toast.success('Profile updated!');
  };

  const handleProfileCancel = () => {
    setTempProfile(profile);
    setEditMode(false);
  };

  const handleUnlike = (movieId: number) => {
    unlikeMutation.mutate(movieId);
  };

  const handleSimilar = (movieId: number) => {
    similarMutation.mutate(movieId);
  };

  const downloadLikedMovies = () => {
    const csvContent = [
      'Movie ID,Title,Year,Genres,Overview',
      ...likedMovies.map(movie => 
        `${movie.movie_id},"${movie.title}",${movie.year || ''},"${(movie.genres || []).join(', ')}","${(movie.overview || '').replace(/"/g, '""')}"`
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `user_${userId}_liked_movies.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast.success('CSV downloaded!');
  };

  const getInitials = (name: string) => {
    return name.trim().slice(0, 1).toUpperCase() || userId.toString().slice(0, 1);
  };

  return (
    <div className="space-y-8">
      {/* Profile Header */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-background-200/50 to-background-300/50 rounded-3xl p-8 border border-white/10"
      >
        <div className="flex flex-col md:flex-row gap-6 items-start">
          {/* Avatar */}
          <div className="flex-shrink-0">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-3xl font-bold text-white shadow-lg">
              {getInitials(profile.display_name)}
            </div>
          </div>

          {/* Profile Info */}
          <div className="flex-grow space-y-4">
            {editMode ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={tempProfile.display_name}
                    onChange={(e) => setTempProfile(prev => ({ ...prev, display_name: e.target.value }))}
                    className="w-full px-4 py-2 bg-background-300 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-500/50"
                    placeholder="Enter your name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Bio
                  </label>
                  <textarea
                    value={tempProfile.bio}
                    onChange={(e) => setTempProfile(prev => ({ ...prev, bio: e.target.value }))}
                    className="w-full px-4 py-2 bg-background-300 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-500/50 h-20 resize-none"
                    placeholder="Tell us about yourself..."
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={handleProfileSave}
                    className="px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white rounded-lg font-medium transition-all duration-200"
                  >
                    Save
                  </button>
                  <button
                    onClick={handleProfileCancel}
                    className="px-4 py-2 bg-background-400 hover:bg-background-300 text-gray-300 rounded-lg font-medium transition-all duration-200"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-gray-400">User ID: {userId}</p>
                  {profile.display_name && (
                    <h1 className="text-2xl font-bold text-white">{profile.display_name}</h1>
                  )}
                  {profile.bio && (
                    <p className="text-gray-300 italic">{profile.bio}</p>
                  )}
                </div>
                <button
                  onClick={() => setEditMode(true)}
                  className="px-4 py-2 bg-background-400 hover:bg-background-300 text-gray-300 rounded-lg font-medium transition-all duration-200 flex items-center gap-2"
                >
                  <User className="w-4 h-4" />
                  Edit Profile
                </button>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="flex-shrink-0">
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-background-400/50 rounded-xl p-4">
                <div className="text-2xl font-bold text-primary-400">{likedMovies.length}</div>
                <div className="text-sm text-gray-400">Liked Movies</div>
              </div>
              <div className="bg-background-400/50 rounded-xl p-4">
                <div className="text-2xl font-bold text-accent-400">{genreStats.length}</div>
                <div className="text-sm text-gray-400">Genres Explored</div>
              </div>
            </div>
          </div>
        </div>
      </motion.section>

      {/* Statistics Section */}
      {likedMovies.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-8"
        >
          {/* Genre Preferences */}
          <div className="bg-gradient-to-br from-background-200/50 to-background-300/50 rounded-2xl p-6 border border-white/10">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-400" />
              Favorite Genres
            </h3>
            <div className="space-y-3">
              {genreStats.map(([genre, count], index) => (
                <div key={genre} className="flex items-center justify-between">
                  <span className="text-gray-300">{genre}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-background-400 rounded-full h-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${(count / genreStats[0][1]) * 100}%` }}
                        transition={{ delay: 0.3 + index * 0.1 }}
                        className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full"
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Era Preferences */}
          <div className="bg-gradient-to-br from-background-200/50 to-background-300/50 rounded-2xl p-6 border border-white/10">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-accent-400" />
              Favorite Eras
            </h3>
            <div className="space-y-3">
              {yearStats.map(([decade, count], index) => (
                <div key={decade} className="flex items-center justify-between">
                  <span className="text-gray-300">{decade}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-background-400 rounded-full h-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${(count / yearStats[0][1]) * 100}%` }}
                        transition={{ delay: 0.3 + index * 0.1 }}
                        className="h-full bg-gradient-to-r from-accent-500 to-primary-500 rounded-full"
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.section>
      )}

      {/* Similar Movies */}
      {similarResults.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Heart className="w-6 h-6 text-accent-400" />
            Similar to: {similarTitle}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {similarResults.map((movie) => (
              <MovieCard
                key={movie.movie_id}
                movie={movie}
                onSimilar={handleSimilar}
                showLike={false}
                showSimilar={false}
              />
            ))}
          </div>
        </motion.section>
      )}

      {/* Liked Movies Section */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Heart className="w-6 h-6 text-red-400" />
            My Liked Movies ({likedMovies.length})
          </h2>
          
          {likedMovies.length > 0 && (
            <button
              onClick={downloadLikedMovies}
              className="px-4 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-600/30 rounded-lg font-medium transition-all duration-200 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Download CSV
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-96 bg-background-300/50 rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : likedMovies.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <Heart className="w-16 h-16 text-gray-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-400 mb-2">
              No liked movies yet
            </h3>
            <p className="text-gray-500">
              Start exploring and liking movies to build your collection!
            </p>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {likedMovies.map((movie) => (
              <MovieCard
                key={movie.movie_id}
                movie={movie}
                onUnlike={handleUnlike}
                onSimilar={handleSimilar}
                showLike={false}
                showUnlike={true}
                showSimilar={true}
                isLiked={true}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default ProfilePage;