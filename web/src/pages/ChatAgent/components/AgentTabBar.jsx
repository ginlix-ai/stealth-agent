import React from 'react';
import { Bot, X } from 'lucide-react';
import { cn } from '../../../lib/utils';
import iconRobo from '../../../assets/img/icon-robo.svg';

/**
 * AgentTabBar Component
 *
 * 底部 Tab 栏，显示所有 agents，可点击切换
 *
 * @param {Array} agents - agents 列表
 * @param {string} selectedAgentId - 当前选中的 agent ID
 * @param {Function} onSelectAgent - 切换 agent 回调
 * @param {Function} onRemoveAgent - 移除 agent 回调
 */
function AgentTabBar({ agents, selectedAgentId, onSelectAgent, onRemoveAgent }) {
  if (agents.length === 0) {
    return null;
  }

  return (
    <div className="flex gap-2 p-0 overflow-x-auto scrollbar-hide min-w-0 justify-center">
      {agents.map((agent, index) => {
        const isSelected = selectedAgentId === agent.id;

        return (
          <div
            key={agent.id}
            className="relative group"
          >
            <button
              onClick={() => onSelectAgent(agent.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all",
                "whitespace-nowrap flex-shrink-0",
                isSelected
                  ? "bg-white/5 text-white"
                  : "bg-transparent text-white/70 hover:bg-white/[0.02]"
              )}
            >
              {/* 头像 */}
              <div className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center",
                isSelected ? "bg-[#6155F5]/20" : "bg-white/10"
              )}>
                <img
                  src={iconRobo}
                  alt="Agent"
                  className="h-4 w-4"
                  style={{
                    filter: isSelected ? 'brightness(0) saturate(100%) invert(44%) sepia(71%) saturate(3645%) hue-rotate(229deg) brightness(98%) contrast(92%)' : 'brightness(0) saturate(100%) invert(100%) opacity(50%)'
                  }}
                />
              </div>

              {/* 编号 + 类型 */}
              <div className="flex flex-col items-start">
                <span className="text-xs font-semibold">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className="text-xs opacity-70">
                  {agent.type || 'Agent'}
                </span>
              </div>
            </button>

            {/* Close button for this agent - shown on hover */}
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onRemoveAgent?.(agent.id);
              }}
              className={cn(
                "absolute top-1 right-1 p-0.5 transition-all",
                "opacity-0 group-hover:opacity-100",
                "hover:bg-white/10 rounded"
              )}
              title="Remove agent"
            >
              <X className="h-3 w-3" style={{ color: 'rgba(255, 255, 255, 0.6)' }} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default AgentTabBar;
