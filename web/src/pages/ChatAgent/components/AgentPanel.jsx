import React from 'react';
import { Bot, CheckCircle2, Circle, Loader2, X } from 'lucide-react';
import { ScrollArea } from '../../../components/ui/scroll-area';
import { cn } from '../../../lib/utils';
import AgentTabBar from './AgentTabBar';
import SubagentCardContent from './SubagentCardContent';

/**
 * AgentPanel Component
 *
 * Right-side panel that displays the selected agent's details and messages.
 * Features:
 * - Shows agent header with status
 * - Displays agent messages using SubagentCardContent
 * - Bottom tab bar for switching between agents
 *
 * @param {Object} props
 * @param {Array} props.agents - Array of agent objects
 * @param {string} props.selectedAgentId - Currently selected agent ID
 * @param {Function} props.onSelectAgent - Callback when agent is selected (pass null to deselect)
 */
function AgentPanel({ agents, selectedAgentId, onSelectAgent }) {
  // Find the selected agent
  const selectedAgent = agents.find(agent => agent.id === selectedAgentId);

  // Don't render if no agents
  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full" style={{ backgroundColor: '#0D0E12' }}>
        <Bot className="h-12 w-12 mb-4" style={{ color: 'rgba(255, 255, 255, 0.3)' }} />
        <p className="text-sm" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>
          No agents running
        </p>
      </div>
    );
  }

  // Don't render if no agent selected
  if (!selectedAgent) {
    return (
      <div className="flex flex-col items-center justify-center h-full" style={{ backgroundColor: '#0D0E12' }}>
        <Bot className="h-12 w-12 mb-4" style={{ color: 'rgba(255, 255, 255, 0.3)' }} />
        <p className="text-sm" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>
          Select an agent to view details
        </p>
      </div>
    );
  }

  /**
   * Get status icon based on agent status
   */
  const getStatusIcon = () => {
    if (selectedAgent.currentTool) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (selectedAgent.status === 'active' && selectedAgent.messages.length > 0) {
      return <Loader2 className="h-4 w-4 animate-spin" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    if (selectedAgent.status === 'completed') {
      return <CheckCircle2 className="h-4 w-4" style={{ color: 'rgba(255, 255, 255, 0.4)' }} />;
    }
    return <Circle className="h-4 w-4" style={{ color: 'rgba(255, 255, 255, 0.3)' }} />;
  };

  /**
   * Get status text
   */
  const getStatusText = () => {
    if (selectedAgent.currentTool) {
      return `Running: ${selectedAgent.currentTool}`;
    }
    if (selectedAgent.status === 'completed') {
      if (selectedAgent.toolCalls > 0) {
        return `Completed (${selectedAgent.toolCalls} tool calls)`;
      }
      return 'Completed';
    }
    if (selectedAgent.status === 'active') {
      if (selectedAgent.messages.length > 0) {
        return 'Running';
      }
      return 'Initializing';
    }
    return 'Initializing';
  };

  return (
    <div
      className="flex flex-col"
      style={{
        background: '#1A1B23',
        width: '100%',
        height: '100%',
        borderRadius: '16px',
        padding: '0 16px 16px',
        boxSizing: 'border-box',
      }}
    >
      {/* Header - Computer Style */}
      <div className="flex-shrink-0 pt-4">
        <div className="pb-4">
          {/* Computer Icon + Title + Close Button */}
          <div className="flex items-center gap-3">
            {/* Computer SVG Icon */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 1024 1024"
              style={{ color: '#6155F5', flexShrink: 0 }}
            >
              <path
                d="M512 132.266667c197.589333 0 291.84 21.333333 333.354667 35.84 2.986667 1.066667 8.96 3.029333 15.018666 6.4 6.698667 3.712 12.117333 8.234667 17.152 13.226666 5.418667 5.376 10.026667 11.093333 13.824 17.962667 3.285333 6.101333 5.376 12.245333 6.613334 15.701333 13.824 38.741333 36.437333 121.472 36.437333 247.978667 0 129.152-23.552 210.56-37.418667 247.253333-1.109333 2.858667-3.114667 8.362667-6.272 13.952-3.498667 6.186667-7.68 11.264-12.416 16.085334a78.506667 78.506667 0 0 1-14.933333 12.288c-5.546667 3.413333-10.794667 5.461333-13.226667 6.4-2.432 1.024-5.12 1.877333-8.021333 2.901333l-12.970667 74.325333c-1.578667 9.045333-3.242667 19.968-10.794666 33.066667-3.456 5.973333-8.192 11.434667-11.52 14.976a77.781333 77.781333 0 0 1-42.752 24.021333c-39.210667 9.130667-114.176 19.754667-252.074667 19.754667s-212.906667-10.666667-252.074667-19.754667a77.738667 77.738667 0 0 1-42.752-24.021333 84.309333 84.309333 0 0 1-11.52-14.933333c-7.552-13.141333-9.216-24.064-10.794666-33.109334l-13.013334-74.325333c-2.858667-1.024-5.546667-1.92-7.978666-2.858667-2.432-1.024-7.68-3.072-13.226667-6.4a78.506667 78.506667 0 0 1-14.933333-12.330666 77.312 77.312 0 0 1-12.416-16.085334c-3.157333-5.546667-5.162667-11.093333-6.229334-13.952-13.909333-36.693333-37.461333-118.101333-37.461333-247.253333 0-126.506667 22.613333-209.237333 36.437333-247.978667 1.28-3.456 3.328-9.6 6.613334-15.701333 3.797333-6.912 8.405333-12.586667 13.824-17.92 5.034667-5.034667 10.453333-9.557333 17.152-13.269333 6.058667-3.370667 12.032-5.333333 15.061333-6.4 41.429333-14.506667 135.68-35.84 333.312-35.84z m248.533333 656.64c-55.125333 9.685333-134.784 17.493333-248.533333 17.493333-113.792 0-193.450667-7.808-248.576-17.493333l7.082667 40.448 0.981333 5.418666 0.426667 1.792 1.024 1.28 1.237333 1.194667c0.64 0.170667 1.493333 0.426667 3.2 0.810667 31.488 7.338667 100.138667 17.749333 234.624 17.749333 134.485333 0 203.093333-10.410667 234.624-17.749333l3.157333-0.810667 1.28-1.194667 1.024-1.28 0.426667-1.834666 0.981333-5.418667 7.04-40.405333z m-11.136 50.56l0.085334-0.085334 0.085333-0.085333-0.213333 0.170667zM512 209.066667c-192.981333 0-277.76 20.992-308.010667 31.573333l-2.218666 0.768-0.469334 0.128-1.408 1.408c-0.384 0.896-0.768 2.005333-1.578666 4.266667C187.306667 278.186667 166.4 352.170667 166.4 469.333333c0 119.594667 21.76 191.744 32.469333 220.032l0.853334 2.176 0.256 0.682667 0.597333 0.64 0.682667 0.64 1.322666 0.597333c27.392 11.008 110.848 35.413333 309.418667 35.413334s282.026667-24.405333 309.418667-35.413334l1.28-0.597333 0.725333-0.64 0.597333-0.64 0.256-0.682667 0.853334-2.133333c10.666667-28.330667 32.426667-100.48 32.426666-220.074667 0-117.162667-20.821333-191.189333-31.872-222.165333l-1.621333-4.266667c-0.128-0.170667-0.341333-0.426667-0.64-0.682666l-0.768-0.725334-0.426667-0.128-2.218666-0.768c-30.293333-10.581333-115.029333-31.573333-308.010667-31.573333z m153.6 362.752v76.8H358.4v-76.8h307.2z m76.8 0h-76.8v-76.8h76.8v76.8z m-384 0H281.6v-76.8h76.8v76.8z m153.642667-76.842667h-76.8V418.133333H512v76.8z m76.8-0.042667H512L512 341.333333h76.8v153.6zM358.4 375.466667H281.6V298.666667h76.8v76.8z m384 0H665.6V298.666667h76.8v76.8z"
                fill="currentColor"
              />
            </svg>

            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium" style={{ color: '#FFFFFF' }}>
                {selectedAgent.name}
              </div>

              {/* Status Bar */}
              <div className="flex items-center gap-2 mt-1">
                {getStatusIcon()}
                <span className="text-xs" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>
                  {getStatusText()}
                </span>
              </div>
            </div>

            {/* Close Button - Deselect current agent */}
            <button
              onClick={() => onSelectAgent(null)}
              className="flex-shrink-0 p-2 rounded-lg transition-colors hover:bg-white/10"
              style={{ color: 'rgba(255, 255, 255, 0.6)' }}
              title="Close agent preview"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Current Tool Display */}
          {selectedAgent.currentTool && (
            <div className="mt-3 flex items-center gap-2 text-xs" style={{ color: 'rgba(255, 255, 255, 0.7)' }}>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 1024 1024"
                style={{ color: '#6155F5' }}
              >
                <path
                  d="M516.266667 85.333333c89.429333 0 171.221333 13.738667 231.978666 37.290667 30.293333 11.733333 57.258667 26.624 77.397334 45.141333 20.138667 18.517333 36.224 43.52 36.266666 74.112v354.133334l-0.085333 0.213333 0.042667 0.213333v177.194667c0 30.592-16.085333 55.594667-36.266667 74.112-20.053333 18.474667-47.104 33.408-77.354667 45.141333-60.757333 23.509333-142.506667 37.290667-231.978666 37.290667-89.472 0-171.178667-13.781333-231.978667-37.290667-30.293333-11.733333-57.301333-26.666667-77.397333-45.141333C186.752 829.226667 170.666667 804.266667 170.666667 773.632V241.877333c0-30.592 16.042667-55.594667 36.224-74.112 20.096-18.517333 47.146667-33.408 77.397333-45.141333C345.088 99.114667 426.794667 85.333333 516.266667 85.333333z"
                  fill="currentColor"
                />
              </svg>
              <span>Running: {selectedAgent.currentTool}</span>
            </div>
          )}
        </div>
      </div>

      {/* Content Area - Scrollable */}
      <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
        <ScrollArea className="h-full w-full">
          <div className="pt-4">
            <SubagentCardContent
              taskId={selectedAgent.taskId}
              description={selectedAgent.description}
              type={selectedAgent.type}
              toolCalls={selectedAgent.toolCalls}
              currentTool={selectedAgent.currentTool}
              status={selectedAgent.status}
              messages={selectedAgent.messages}
              isHistory={false}
            />
          </div>
        </ScrollArea>
      </div>

      {/* Bottom Tab Bar */}
      {agents.length > 1 && (
        <div className="flex-shrink-0">
          <AgentTabBar
            agents={agents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={onSelectAgent}
          />
        </div>
      )}
    </div>
  );
}

export default AgentPanel;
