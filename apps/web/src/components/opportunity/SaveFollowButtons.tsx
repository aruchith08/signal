import React from 'react';
import { Bookmark, Bell } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

interface SaveFollowButtonsProps {
  opportunityId: string;
  title?: string;
  size?: 'sm' | 'md';
}

export const SaveFollowButtons: React.FC<SaveFollowButtonsProps> = ({
  opportunityId,
  title,
  size = 'md',
}) => {
  const { isSaved, isFollowed, toggleSave, toggleFollow } = useAuth();
  const saved = isSaved(opportunityId);
  const followed = isFollowed(opportunityId);

  const handleSaveClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleSave(opportunityId, title);
  };

  const handleFollowClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleFollow(opportunityId, title);
  };

  const buttonPadding = size === 'sm' ? 'px-2 py-1 text-xs' : 'px-2.5 py-1.5 text-xs';

  return (
    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      {/* Save / Bookmark Button */}
      <button
        onClick={handleSaveClick}
        title={saved ? 'Remove from saved' : 'Save opportunity'}
        className={`inline-flex items-center gap-1.5 rounded-lg border font-medium transition-all ${buttonPadding} ${
          saved
            ? 'bg-amber-950/40 border-amber-600/50 text-amber-300 hover:bg-amber-900/40'
            : 'bg-slate-900/60 border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-600'
        }`}
      >
        <Bookmark className={`w-3.5 h-3.5 ${saved ? 'fill-amber-400 text-amber-400' : ''}`} />
        <span>{saved ? 'Saved' : 'Save'}</span>
      </button>

      {/* Follow / Track Button */}
      <button
        onClick={handleFollowClick}
        title={followed ? 'Unfollow updates' : 'Follow for deadline alerts'}
        className={`inline-flex items-center gap-1.5 rounded-lg border font-medium transition-all ${buttonPadding} ${
          followed
            ? 'bg-sky-950/40 border-sky-600/50 text-sky-300 hover:bg-sky-900/40'
            : 'bg-slate-900/60 border-slate-700/60 text-slate-400 hover:text-slate-200 hover:border-slate-600'
        }`}
      >
        <Bell className={`w-3.5 h-3.5 ${followed ? 'fill-sky-400 text-sky-400' : ''}`} />
        <span>{followed ? 'Following' : 'Follow'}</span>
      </button>
    </div>
  );
};
