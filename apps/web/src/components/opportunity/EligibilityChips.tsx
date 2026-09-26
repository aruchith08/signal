import React from 'react';
import { Globe, Users, Award, Code2 } from 'lucide-react';
import { Badge } from '../common/Badge';

interface EligibilityChipsProps {
  country?: string | null;
  targetAudience?: string | null;
  eligibility?: string | null;
  requiredSkills?: string[] | null;
  tags?: string[] | null;
  maxSkills?: number;
}

export const EligibilityChips: React.FC<EligibilityChipsProps> = ({
  country,
  targetAudience,
  eligibility,
  requiredSkills = [],
  tags = [],
  maxSkills = 3,
}) => {
  const visibleSkills = (requiredSkills || []).slice(0, maxSkills);
  const remainingSkillsCount = (requiredSkills || []).length - maxSkills;

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      {/* Country / Geographic Scope */}
      {country && (
        <Badge variant="outline" size="xs" className="gap-1 text-slate-300">
          <Globe className="w-3 h-3 text-slate-400" />
          <span>{country}</span>
        </Badge>
      )}

      {/* Target Audience / Education */}
      {targetAudience && (
        <Badge variant="outline" size="xs" className="gap-1 text-slate-300">
          <Users className="w-3 h-3 text-slate-400" />
          <span className="truncate max-w-[140px]">{targetAudience}</span>
        </Badge>
      )}

      {/* Eligibility summary */}
      {eligibility && !targetAudience && (
        <Badge variant="outline" size="xs" className="gap-1 text-slate-300">
          <Award className="w-3 h-3 text-slate-400" />
          <span className="truncate max-w-[140px]">{eligibility}</span>
        </Badge>
      )}

      {/* Required Skills */}
      {visibleSkills.map((skill) => (
        <Badge key={skill} variant="slate" size="xs" className="gap-1 text-slate-300 font-mono">
          <Code2 className="w-2.5 h-2.5 text-emerald-400" />
          <span>{skill}</span>
        </Badge>
      ))}

      {remainingSkillsCount > 0 && (
        <span className="text-[10px] text-slate-500 font-mono">
          +{remainingSkillsCount} more
        </span>
      )}

      {/* Tags if no skills */}
      {visibleSkills.length === 0 && (tags || []).slice(0, 2).map(tag => (
        <Badge key={tag} variant="slate" size="xs" className="text-slate-400 font-mono">
          #{tag}
        </Badge>
      ))}
    </div>
  );
};
