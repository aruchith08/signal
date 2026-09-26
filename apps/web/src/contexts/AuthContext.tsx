import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types/user';
import { getActiveUser } from '../services/api/users';
import { 
  getUserInteractions, 
  saveOpportunity, 
  unsaveOpportunity, 
  followOpportunity, 
  unfollowOpportunity 
} from '../services/api/interactions';
import { useToast } from './ToastContext';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  savedIds: Set<string>;
  followedIds: Set<string>;
  isSaved: (opportunityId: string) => boolean;
  isFollowed: (opportunityId: string) => boolean;
  toggleSave: (opportunityId: string, title?: string) => Promise<void>;
  toggleFollow: (opportunityId: string, title?: string) => Promise<void>;
  refreshInteractions: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [followedIds, setFollowedIds] = useState<Set<string>>(new Set());
  const { showToast } = useToast();

  const loadUserAndInteractions = useCallback(async () => {
    try {
      setLoading(true);
      const activeUser = await getActiveUser();
      setUser(activeUser);

      if (activeUser && activeUser.id) {
        try {
          const interactions = await getUserInteractions(activeUser.id);
          setSavedIds(new Set(interactions.saved_opportunity_ids || []));
          setFollowedIds(new Set(interactions.followed_opportunity_ids || []));
        } catch (err) {
          console.warn('Could not load interactions:', err);
        }
      }
    } catch (err) {
      console.error('Failed to bootstrap active user:', err);
      showToast('Backend Connection Notice', {
        description: 'Unable to reach SIGNAL backend API. Ensure service is operational.',
        type: 'warning',
      });
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadUserAndInteractions();
  }, [loadUserAndInteractions]);

  const isSaved = useCallback((opportunityId: string) => {
    return savedIds.has(opportunityId);
  }, [savedIds]);

  const isFollowed = useCallback((opportunityId: string) => {
    return followedIds.has(opportunityId);
  }, [followedIds]);

  const toggleSave = useCallback(async (opportunityId: string, title?: string) => {
    if (!user) {
      showToast('Action Failed', { description: 'No active student user profile loaded', type: 'error' });
      return;
    }

    const currentlySaved = savedIds.has(opportunityId);
    // Optimistic UI update
    setSavedIds(prev => {
      const next = new Set(prev);
      if (currentlySaved) next.delete(opportunityId);
      else next.add(opportunityId);
      return next;
    });

    try {
      if (currentlySaved) {
        await unsaveOpportunity(user.id, opportunityId);
        showToast('Removed from Bookmarks', {
          description: title ? `Removed "${title}"` : 'Opportunity unsaved',
          type: 'info'
        });
      } else {
        await saveOpportunity(user.id, opportunityId);
        showToast('Saved to Bookmarks', {
          description: title ? `Saved "${title}"` : 'Opportunity bookmarked',
          type: 'success'
        });
      }
    } catch (err: any) {
      // Revert optimistic update
      setSavedIds(prev => {
        const next = new Set(prev);
        if (currentlySaved) next.add(opportunityId);
        else next.delete(opportunityId);
        return next;
      });
      showToast('Bookmark update failed', { description: err.message, type: 'error' });
    }
  }, [user, savedIds, showToast]);

  const toggleFollow = useCallback(async (opportunityId: string, title?: string) => {
    if (!user) {
      showToast('Action Failed', { description: 'No active student user profile loaded', type: 'error' });
      return;
    }

    const currentlyFollowed = followedIds.has(opportunityId);
    // Optimistic UI update
    setFollowedIds(prev => {
      const next = new Set(prev);
      if (currentlyFollowed) next.delete(opportunityId);
      else next.add(opportunityId);
      return next;
    });

    try {
      if (currentlyFollowed) {
        await unfollowOpportunity(user.id, opportunityId);
        showToast('Unfollowed', {
          description: title ? `Stopped monitoring "${title}"` : 'Stopped monitoring opportunity',
          type: 'info'
        });
      } else {
        await followOpportunity(user.id, opportunityId);
        showToast('Following Opportunity', {
          description: title ? `Tracking timeline & deadline alerts for "${title}"` : 'Subscribed to deadline updates',
          type: 'success'
        });
      }
    } catch (err: any) {
      // Revert optimistic update
      setFollowedIds(prev => {
        const next = new Set(prev);
        if (currentlyFollowed) next.add(opportunityId);
        else next.delete(opportunityId);
        return next;
      });
      showToast('Follow update failed', { description: err.message, type: 'error' });
    }
  }, [user, followedIds, showToast]);

  const refreshInteractions = useCallback(async () => {
    if (user?.id) {
      try {
        const interactions = await getUserInteractions(user.id);
        setSavedIds(new Set(interactions.saved_opportunity_ids || []));
        setFollowedIds(new Set(interactions.followed_opportunity_ids || []));
      } catch (err) {
        console.warn('Failed to refresh interactions', err);
      }
    }
  }, [user?.id]);

  const refreshUser = useCallback(async () => {
    await loadUserAndInteractions();
  }, [loadUserAndInteractions]);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        savedIds,
        followedIds,
        isSaved,
        isFollowed,
        toggleSave,
        toggleFollow,
        refreshInteractions,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
