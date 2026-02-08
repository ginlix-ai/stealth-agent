import React, { useState, useRef, useEffect } from 'react';
import { Bot, X, CheckCircle2, MoreHorizontal, Check } from 'lucide-react';
import { cn } from '../../../lib/utils';
import iconRoboSing from '../../../assets/img/icon-robo-sing.svg';
import iconKing from '../../../assets/img/icon-king.svg';
import './AgentTabBar.css';

/**
 * AgentTabBar Component
 *
 * Bottom tab bar displaying all agents, clickable to switch
 * - Fixed width, compact layout
 * - Shows avatar and name only, vertically centered
 * - Active state pulsing animation
 * - Completed state shows white check icon (no circle)
 * - Delete button at top-right, high z-index
 * - Hover and selected background is light white
 * - Completed agent has no background
 * - Centered display, shows more button when overflow
 *
 * @param {Array} agents - List of agents
 * @param {string} selectedAgentId - Currently selected agent ID
 * @param {Function} onSelectAgent - Callback when agent is selected
 * @param {Function} onRemoveAgent - Callback when agent is removed
 */
function AgentTabBar({ agents, selectedAgentId, onSelectAgent, onRemoveAgent }) {
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [visibleCount, setVisibleCount] = useState(agents.length);
  const containerRef = useRef(null);
  const menuRef = useRef(null);

  // Calculate how many agents can fit based on container width
  useEffect(() => {
    const calculateVisibleCount = () => {
      if (!containerRef.current) return;
      
      const containerWidth = containerRef.current.offsetWidth;
      const tabWidth = 61; // 60px width + 1px gap
      const moreButtonWidth = 49; // More button width (48px + 1px gap)
      // More button is on the left, so we need to reserve space for it
      const availableWidth = containerWidth - moreButtonWidth;
      const maxVisible = Math.max(0, Math.floor(availableWidth / tabWidth));
      
      if (maxVisible > 0 && maxVisible < agents.length) {
        setVisibleCount(maxVisible);
      } else {
        setVisibleCount(agents.length);
      }
    };

    calculateVisibleCount();
    window.addEventListener('resize', calculateVisibleCount);
    return () => window.removeEventListener('resize', calculateVisibleCount);
  }, [agents.length]);

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowMoreMenu(false);
      }
    };
    if (showMoreMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showMoreMenu]);

  if (agents.length === 0) {
    return null;
  }

  const visibleAgents = agents.slice(0, visibleCount);
  const hiddenAgents = agents.slice(visibleCount);

  return (
    <div className="relative flex items-center justify-center" ref={containerRef}>
      {/* More button - shown when there are hidden agents, placed on the left */}
      {hiddenAgents.length > 0 && (
        <div className="relative flex-shrink-0 mr-1" ref={menuRef}>
          <button
            onClick={() => setShowMoreMenu(!showMoreMenu)}
            className="flex flex-col items-center justify-center gap-1 px-1.5 py-2 rounded-lg transition-all w-12"
            style={{
              backgroundColor: showMoreMenu ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
            }}
            onMouseEnter={(e) => {
              if (!showMoreMenu) {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
              }
            }}
            onMouseLeave={(e) => {
              if (!showMoreMenu) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            <MoreHorizontal className="h-4 w-4" style={{ color: 'rgba(255, 255, 255, 0.7)' }} />
            <span className="text-xs font-medium" style={{ color: 'rgba(255, 255, 255, 0.7)' }}>
              {hiddenAgents.length}
            </span>
          </button>

          {/* More menu dropdown */}
          {showMoreMenu && (
            <div
              className="absolute bottom-full right-0 mb-2 rounded-lg shadow-lg overflow-hidden"
              style={{
                backgroundColor: 'rgba(15, 20, 34, 0.95)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                minWidth: '160px',
                maxHeight: '300px',
                overflowY: 'auto',
                zIndex: 1000,
              }}
            >
              {hiddenAgents.map((agent) => {
                const isSelected = selectedAgentId === agent.id;
                const isCompleted = agent.status === 'completed';
                const isMainAgent = agent.id === 'main' || agent.isMainAgent;
                const agentIcon = isMainAgent ? iconKing : iconRoboSing;
                
                return (
                  <button
                    key={agent.id}
                    onClick={() => {
                      onSelectAgent(agent.id);
                      setShowMoreMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-white/5"
                    style={{
                      backgroundColor: isSelected ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                      color: isSelected ? '#FFFFFF' : 'rgba(255, 255, 255, 0.7)',
                    }}
                  >
                    <div className="relative flex-shrink-0">
                      <div
                        className="w-6 h-6 rounded flex items-center justify-center"
                        style={{
                          backgroundColor: isCompleted ? 'transparent' : 'rgba(255, 255, 255, 0.1)',
                        }}
                      >
                        <img
                          src={agentIcon}
                          alt="Agent"
                          className="h-3.5 w-3.5"
                          style={{
                            filter: 'brightness(0) saturate(100%) invert(100%) opacity(50%)'
                          }}
                        />
                      </div>
                      {isCompleted && (
                        <Check 
                          className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5" 
                          style={{ color: '#FFFFFF' }} 
                        />
                      )}
                    </div>
                    <span className="text-sm font-medium truncate flex-1">{agent.name}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-1 p-0 overflow-hidden min-w-0">
        {visibleAgents.map((agent) => {
          const isSelected = selectedAgentId === agent.id;
          const isActive = agent.status === 'active' && agent.isActive;
          const isCompleted = agent.status === 'completed';
          const canRemove = true; // All agents can be removed
          const isMainAgent = agent.id === 'main' || agent.isMainAgent;
          const agentIcon = isMainAgent ? iconKing : iconRoboSing;

          return (
            <div
              key={agent.id}
              className="relative group flex-shrink-0"
              style={{ width: '60px' }}
            >
              <button
                onClick={() => onSelectAgent(agent.id)}
                className="flex flex-col items-center justify-center gap-1 px-1.5 py-2 rounded-lg transition-all w-full"
                style={{
                  backgroundColor: isSelected ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  } else {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
                  }
                }}
              >
                {/* Avatar container - relative positioning for completion icon */}
                <div className="relative">
                  {!isCompleted && (
                    <div
                      className={cn(
                        "w-9 h-9 rounded-lg flex items-center justify-center transition-all",
                        isActive && "agent-tab-active-pulse"
                      )}
                      style={{
                        backgroundColor: isActive ? 'rgba(15, 237, 190, 0.25)' : 'rgba(255, 255, 255, 0.1)',
                      }}
                    >
                      <img
                        src={agentIcon}
                        alt="Agent"
                        className="h-5 w-5"
                        style={{
                          filter: isSelected ? 'brightness(0) saturate(100%) invert(100%)' : 'brightness(0) saturate(100%) invert(100%) opacity(50%)'
                        }}
                      />
                    </div>
                  )}
                  {isCompleted && (
                    <div
                      className={cn(
                        "w-9 h-9 rounded-lg flex items-center justify-center transition-all relative",
                        isActive && "agent-tab-active-pulse"
                      )}
                    >
                      <img
                        src={agentIcon}
                        alt="Agent"
                        className="h-5 w-5"
                        style={{
                          filter: isSelected ? 'brightness(0) saturate(100%) invert(100%)' : 'brightness(0) saturate(100%) invert(100%) opacity(50%)'
                        }}
                      />
                      {/* Completion icon - bottom-right corner, white check icon */}
                      <Check 
                        className="absolute -bottom-0.5 -right-0.5 h-3 w-3" 
                        style={{ color: '#FFFFFF', zIndex: 10 }} 
                      />
                    </div>
                  )}
                </div>

                {/* Name */}
                <span
                  className={cn(
                    "text-xs font-medium text-center truncate w-full",
                    isSelected ? "text-white" : "text-white/70"
                  )}
                  style={{ lineHeight: '1.2' }}
                >
                  {agent.name}
                </span>
              </button>

              {/* Close button - top-right corner, visible style, shown on hover */}
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onRemoveAgent?.(agent.id);
                }}
                className={cn(
                  "absolute top-0 right-0 w-4 h-4 rounded-full flex items-center justify-center transition-all",
                  "opacity-0 group-hover:opacity-100"
                )}
                style={{
                  zIndex: 200,
                  transform: 'translate(calc(25% - 4px), calc(-25% + 2px))',
                  backgroundColor: 'transparent',
                }}
                title="Remove from tag bar"
              >
                <X className="h-3 w-3" style={{ color: '#FFFFFF', strokeWidth: 2.5 }} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AgentTabBar;
