import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { updateUserProfile, updateUserPreferences } from '../services/api/users';
import { Card } from '../components/common/Card';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { useToast } from '../contexts/ToastContext';
import { 
  User, 
  Settings, 
  Send, 
  Sliders, 
  Code2, 
  Plus, 
  X, 
  Check, 
  Moon, 
  Sparkles,
  ExternalLink 
} from 'lucide-react';

export const ProfilePage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const { showToast } = useToast();

  const [saving, setSaving] = useState(false);

  // Form states
  const [headline, setHeadline] = useState('');
  const [bio, setBio] = useState('');
  const [github, setGithub] = useState('');
  const [threshold, setThreshold] = useState(0.5);
  const [quietHours, setQuietHours] = useState(false);
  const [quietStart, setQuietStart] = useState('23:00');
  const [quietEnd, setQuietEnd] = useState('08:00');
  const [telegramChatId, setTelegramChatId] = useState('');

  // Skills
  const [skills, setSkills] = useState<string[]>(['Python', 'FastAPI', 'React', 'Machine Learning', 'Algorithms']);
  const [newSkill, setNewSkill] = useState('');

  // Interest weights
  const [weights, setWeights] = useState<Record<string, number>>({
    'Artificial Intelligence': 0.95,
    'Competitive Programming': 0.85,
    'Systems & Infrastructure': 0.75,
    'Web & Fullstack': 0.80,
    'Open Source': 0.70,
  });

  useEffect(() => {
    if (user) {
      setHeadline(user.profile?.headline || 'CS Undergraduate & Competitive Programmer');
      setBio(user.profile?.bio || 'Passionate about distributed systems, AI hackathons, and algorithmic contests.');
      setGithub(user.profile?.github_username || 'alexchen');
      setThreshold(user.relevance_threshold || 0.5);
      setTelegramChatId(user.telegram_chat_id || '987654321');
      if (user.preferences) {
        setQuietHours(!!user.preferences.quiet_hours_enabled);
        setQuietStart(user.preferences.quiet_hours_start || '23:00');
        setQuietEnd(user.preferences.quiet_hours_end || '08:00');
        if (user.preferences.interest_weights) {
          setWeights(user.preferences.interest_weights);
        }
      }
    }
  }, [user]);

  const handleAddSkill = (e: React.FormEvent) => {
    e.preventDefault();
    if (newSkill.trim() && !skills.includes(newSkill.trim())) {
      setSkills([...skills, newSkill.trim()]);
      setNewSkill('');
    }
  };

  const handleRemoveSkill = (skillToRemove: string) => {
    setSkills(skills.filter((s) => s !== skillToRemove));
  };

  const handleWeightChange = (interest: string, value: number) => {
    setWeights((prev) => ({ ...prev, [interest]: value }));
  };

  const handleSaveAll = async () => {
    if (!user?.id) return;
    setSaving(true);
    try {
      await Promise.all([
        updateUserProfile(user.id, {
          headline,
          bio,
          github_username: github,
          interests: Object.keys(weights),
        }),
        updateUserPreferences(user.id, {
          min_relevance_score: threshold,
          quiet_hours_enabled: quietHours,
          quiet_hours_start: quietStart,
          quiet_hours_end: quietEnd,
          interest_weights: weights,
        }),
      ]);
      await refreshUser();
      showToast('Profile & Preferences Saved', {
        description: 'Relevance scoring and alert thresholds updated.',
        type: 'success',
      });
    } catch (err: any) {
      showToast('Save Failed', { description: err.message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-slate-100 tracking-tight">
            STUDENT PROFILE & INTELLIGENCE PREFERENCES
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Configure your academic profile, skill inventory, and personalization weights.
          </p>
        </div>

        <Button variant="primary" size="sm" loading={saving} onClick={handleSaveAll}>
          <Check className="w-4 h-4" />
          Save Preferences
        </Button>
      </div>

      {/* Academic Identity Card */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Academic & Identity Profile
            </h3>
          </div>
          <Badge variant="success" size="xs">
            Verified Student Profile
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Full Name"
            value={user?.name || ''}
            disabled
            hint="Deterministic user account identifier"
          />
          <Input
            label="Email"
            value={user?.email || 'alex.chen@university.edu'}
            disabled
          />
          <Input
            label="Degree Program"
            value={user?.education_level || 'B.Tech Computer Science'}
            disabled
          />
          <Input
            label="Graduation Year"
            value={user?.graduation_year?.toString() || '2026'}
            disabled
          />
        </div>

        <div className="space-y-3 pt-2">
          <Input
            label="Headline"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. CS Student • AI Hackathon Competitor"
          />
          <Input
            label="GitHub Profile Handle"
            value={github}
            onChange={(e) => setGithub(e.target.value)}
            placeholder="alexchen"
          />
        </div>
      </Card>

      {/* Skills Inventory */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Code2 className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Skills Inventory
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {skills.length} skills indexed
          </span>
        </div>

        <p className="text-xs text-slate-400">
          The relevance engine matches these skills against opportunity requirements (e.g. hackathons, research fellowships).
        </p>

        {/* Existing skills */}
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => (
            <span
              key={skill}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 text-xs font-mono border border-slate-700/80"
            >
              <span>{skill}</span>
              <button
                type="button"
                onClick={() => handleRemoveSkill(skill)}
                className="text-slate-400 hover:text-rose-400 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          ))}
        </div>

        {/* Add skill form */}
        <form onSubmit={handleAddSkill} className="flex gap-2 max-w-sm pt-2">
          <Input
            placeholder="Add skill (e.g. PyTorch, Rust)..."
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
          />
          <Button type="submit" variant="secondary" size="sm">
            <Plus className="w-4 h-4" />
            Add
          </Button>
        </form>
      </Card>

      {/* Weighted Interest Matrix */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Weighted Interest Matrix
            </h3>
          </div>
          <Badge variant="purple" size="xs">
            Dynamic Ranking
          </Badge>
        </div>

        <p className="text-xs text-slate-400">
          Adjust the relative importance weights for each interest category. The engine scales match scores accordingly.
        </p>

        <div className="space-y-4 pt-2">
          {Object.entries(weights).map(([interest, weight]) => (
            <div key={interest} className="space-y-1.5">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-200">{interest}</span>
                <span className="text-emerald-400 font-bold">{Math.round(weight * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weight}
                onChange={(e) => handleWeightChange(interest, parseFloat(e.target.value))}
                className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg appearance-none"
              />
            </div>
          ))}
        </div>
      </Card>

      {/* Relevance Threshold & Alert Controls */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
              Alert Intelligence & Relevance Threshold
            </h3>
          </div>
          <span className="text-xs font-mono text-emerald-400 font-bold">
            {Math.round(threshold * 100)}%
          </span>
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-medium text-slate-300">
            Minimum Opportunity Relevance Threshold
          </label>
          <input
            type="range"
            min="0.1"
            max="0.95"
            step="0.05"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg appearance-none"
          />
          <p className="text-[11px] text-slate-400 font-mono">
            Opportunities scoring below {Math.round(threshold * 100)}% will not appear in your priority alerts.
          </p>
        </div>

        {/* Telegram Integration */}
        <div className="pt-4 border-t border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4 text-sky-400" />
              <span className="text-xs font-semibold text-slate-200">
                Telegram Alert Channel
              </span>
            </div>
            <Badge variant="info" size="xs">
              Connected
            </Badge>
          </div>
          <Input
            label="Telegram Chat ID"
            value={telegramChatId}
            onChange={(e) => setTelegramChatId(e.target.value)}
            hint="Configured for Phase 2 real-time dispatch"
          />
        </div>

        {/* Quiet Hours */}
        <div className="pt-4 border-t border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Moon className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-semibold text-slate-200">
                Quiet Hours (Suppress Non-Critical Alerts)
              </span>
            </div>
            <input
              type="checkbox"
              checked={quietHours}
              onChange={(e) => setQuietHours(e.target.checked)}
              className="accent-emerald-500 h-4 w-4 rounded cursor-pointer"
            />
          </div>
          {quietHours && (
            <div className="flex items-center gap-4 text-xs font-mono pt-1">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Start:</span>
                <input
                  type="time"
                  value={quietStart}
                  onChange={(e) => setQuietStart(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-400">End:</span>
                <input
                  type="time"
                  value={quietEnd}
                  onChange={(e) => setQuietEnd(e.target.value)}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200"
                />
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
