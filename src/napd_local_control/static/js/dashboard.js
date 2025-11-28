/**
 * SIA Local Control Dashboard JavaScript
 * Handles WebSocket communication and UI updates
 */

class Dashboard {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectDelay = 4000;
        this.data = {};
        this.selectedPump = 1; // Default to pump 1
        
        // Connection timeout settings
        this.connectionTimeout = 5 * 60 * 1000; // 5 minutes in milliseconds
        this.connectionTimeoutId = null;
        
        this.initializeElements();
        this.initializeSocket();
        this.setupEventListeners();
        this.updatePumpSelection();
        this.startConnectionTimeout();
    }
    
    initializeElements() {
        // Connection status
        this.connectionStatus = document.getElementById('connection-status');
        
        // Pump controls
        this.targetRate = document.getElementById('target-rate').querySelector('.value');
        this.flowRate = document.getElementById('flow-rate').querySelector('.value');
        this.pumpState = document.getElementById('pump-state').querySelector('.state-value');
        
        // Pump 2 controls
        this.targetRate2 = document.getElementById('target-rate-2').querySelector('.value');
        this.flowRate2 = document.getElementById('flow-rate-2').querySelector('.value');
        this.pumpState2 = document.getElementById('pump-state-2').querySelector('.state-value');
        
        // Solar controls
        this.batteryVoltage = document.getElementById('battery-voltage').querySelector('.value');
        this.batteryPercentage = document.getElementById('battery-percentage').querySelector('.value');
        this.batteryProgress = document.getElementById('battery-progress');
        this.arrayVoltage = document.getElementById('array-voltage').querySelector('.value');
        this.batteryAh = document.getElementById('battery-ah').querySelector('.value');
        
        // Tank controls
        this.tankLevelMm = document.getElementById('tank-level-mm').querySelector('.value');
        this.tankLevelPercent = document.getElementById('tank-level-percent').querySelector('.value');
        this.tankProgress = document.getElementById('tank-progress');
        
        // Skid controls
        this.skidFlow = document.getElementById('skid-flow').querySelector('.value');
        this.skidPressure = document.getElementById('skid-pressure').querySelector('.value');
        
        this.systemStatus = document.getElementById('system-status')?.querySelector('.status-value');
        
        // Footer
        this.lastUpdate = document.getElementById('last-update');
        
        // Loading overlay
        this.loadingOverlay = document.getElementById('loading-overlay');
        
        // Pump control elements
        this.pumpControl1 = document.getElementById('pump-control-1');
        this.pumpControl2 = document.getElementById('pump-control-2');
        
        // Fault popover
        this.faultPopover = document.getElementById('fault-popover');
        this.faultMessageList = document.getElementById('fault-message-list');
        this.faultInstructions = document.querySelector('.fault-popover-instructions');
    }
    
    initializeSocket() {
        try {
            this.socket = io();
            this.setupSocketEvents();
        } catch (error) {
            console.error('Failed to initialize socket:', error);
            this.showConnectionError();
        }
    }
    
    setupSocketEvents() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('Connected to dashboard server');
            this.isConnected = true;
            this.updateConnectionStatus(true);
            this.hideLoadingOverlay();
            this.clearConnectionTimeout(); // Clear the timeout since we're connected
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from dashboard server');
            this.isConnected = false;
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.updateConnectionStatus(false);
            this.showConnectionError();
        });
        
        // Data events
        this.socket.on('data_update', (data) => {
            console.log('Received data update:', data);
            this.data = data;
            this.updateDashboard(data);
            this.updateLastUpdateTime();
        });
        
        this.socket.on('heartbeat', (data) => {
            console.log('Received heartbeat:', data);
            this.updateLastUpdateTime(data.timestamp);
        });
        
        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.showError(error.message || 'Unknown error occurred');
        });
        
        // Pump selection events
        this.socket.on('pump_selection_changed', (data) => {
            console.log('Received pump selection change:', data);
            if (data.selected_pump) {
                this.setSelectedPump(data.selected_pump, true); // true = fromWebSocket
            }
        });
    }
    
    setupEventListeners() {
        // Pump state buttons
        const pumpStateButtons = document.querySelectorAll('.state-btn[data-state]');
        pumpStateButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const state = e.target.getAttribute('data-state');
                this.changePumpState(state);
            });
        });
        
        // Request initial data
        setTimeout(() => {
            if (this.isConnected) {
                this.socket.emit('request_data');
                // Request current pump selection
                this.socket.emit('request_pump_selection');
            }
        }, 1000);
    }
    
    updateConnectionStatus(connected) {
        if (connected) {
            this.connectionStatus.innerHTML = '<i class="fas fa-circle"></i> Connected';
            this.connectionStatus.className = 'status-connected';
        } else {
            this.connectionStatus.innerHTML = '<i class="fas fa-circle"></i> Disconnected';
            this.connectionStatus.className = 'status-disconnected';
        }
    }
    
    updateDashboard(data) {
        // Update pump data
        if (data.pump) {
            this.updatePumpData(data.pump);
        }
        
        // Update pump 2 data
        if (data.pump2) {
            this.updatePump2Data(data.pump2);
        }
        
        // Update solar data
        if (data.solar) {
            this.updateSolarData(data.solar);
        }
        
        // Update tank data
        if (data.tank) {
            this.updateTankData(data.tank);
        }
        
        // Update skid data
        if (data.skid) {
            this.updateSkidData(data.skid);
        }
        
        // Update system data
        if (data.system) {
            this.updateSystemData(data.system);
        }
        
        // Update faults
        if (data.faults) {
            this.updateFaults(data.faults);
        } else {
            this.updateFaults({});
        }
    }
    
    updatePumpData(pumpData) {
        // Update target rate
        if (pumpData.target_rate !== undefined) {
            this.updateValueChange(this.targetRate, pumpData.target_rate.toFixed(2));
        }
        
        // Update flow rate
        if (pumpData.flow_rate !== undefined) {
            this.updateValueChange(this.flowRate, pumpData.flow_rate.toFixed(2));
        }
        
        // Update pump state
        if (pumpData.pump_state !== undefined) {
            this.updatePumpState(pumpData.pump_state);
        }
    }
    
    updatePump2Data(pump2Data) {
        // Update target rate
        if (pump2Data.target_rate !== undefined) {
            this.updateValueChange(this.targetRate2, pump2Data.target_rate.toFixed(2));
        }
        
        // Update flow rate
        if (pump2Data.flow_rate !== undefined) {
            this.updateValueChange(this.flowRate2, pump2Data.flow_rate.toFixed(2));
        }
        
        // Update pump state
        if (pump2Data.pump_state !== undefined) {
            this.updatePump2State(pump2Data.pump_state);
        }
    }
    
    updateSolarData(solarData) {
        // Update battery voltage
        if (solarData.battery_voltage !== undefined) {
            this.animateValueChange(this.batteryVoltage, solarData.battery_voltage.toFixed(1));
        }
        
        // Update battery percentage
        if (solarData.battery_percentage !== undefined) {
            const percentage = Math.round(solarData.battery_percentage);
            this.animateValueChange(this.batteryPercentage, percentage.toString());
            this.updateProgressBar(this.batteryProgress, percentage);
        }
        
        // Update panel power
        if (solarData.panel_power !== undefined) {
            this.animateValueChange(this.arrayVoltage, solarData.panel_power.toFixed(1));
        }
        
        // Update battery Ah
        if (solarData.battery_ah !== undefined) {
            this.animateValueChange(this.batteryAh, solarData.battery_ah.toFixed(1));
        }
    }
    
    updateTankData(tankData) {
        // Update tank level in mm
        if (tankData.tank_level_mm !== undefined) {
            this.updateValueChange(this.tankLevelMm, Math.round(tankData.tank_level_mm).toString());
        }
        
        // Update tank level percentage
        if (tankData.tank_level_percent !== undefined) {
            const percentage = Math.round(tankData.tank_level_percent);
            this.updateValueChange(this.tankLevelPercent, percentage.toString());
            this.updateProgressBar(this.tankProgress, percentage);
        }
    }
    
    updateSkidData(skidData) {
        // Update skid flow
        // if (skidData.skid_flow !== undefined) {
        //     this.updateValueChange(this.skidFlow, skidData.skid_flow.toFixed(1));
        // }
        
        // Update skid pressure
        if (skidData.skid_pressure !== undefined) {
            this.updateValueChange(this.skidPressure, skidData.skid_pressure.toFixed(1));
        }
    }
    
    updateSystemData(systemData) {
        // Update system status
        if (systemData.status !== undefined) {
            this.updateSystemStatus(systemData.status);
        }
    }
    
    updateFaults(faultData = {}) {
        if (!this.faultPopover || !this.faultMessageList) {
            return;
        }
        
        const messages = [];
        if (faultData.hh_pressure) {
            messages.push('High High Pressure Tripped the Pumps!');
        }
        if (faultData.ll_tank_level) {
            messages.push('Low Low Tank Level Tripped the Pumps! - Fill Tank');
        }
        
        this.faultMessageList.innerHTML = '';
        
        if (messages.length > 0) {
            messages.forEach(message => {
                const item = document.createElement('li');
                item.textContent = message;
                this.faultMessageList.appendChild(item);
            });
            
            if (this.faultInstructions) {
                this.faultInstructions.textContent = 'Press the selector button to clear the faults.';
            }
            
            this.faultPopover.classList.remove('hidden');
        } else {
            this.faultPopover.classList.add('hidden');
        }
    }
    
    updatePumpState(state) {
        this.pumpState.textContent = state;
        this.pumpState.className = `state-value ${state}`;
        
        // Update active button
        const buttons = document.querySelectorAll('.state-btn');
        buttons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-state') === state) {
                btn.classList.add('active');
            }
        });
    }
    
    updatePump2State(state) {
        this.pumpState2.textContent = state;
        this.pumpState2.className = `state-value ${state}`;
        
        // Note: If pump2 has its own control buttons, you would update them here
        // For now, pump2 state is display-only
    }
    
    updateProgressBar(progressBar, percentage) {
        progressBar.style.width = `${Math.max(0, Math.min(100, percentage))}%`;
        
        // Update color based on percentage
        progressBar.className = 'progress-fill';
        if (percentage < 5) {
            progressBar.classList.add('low');
        } else if (percentage < 15) {
            progressBar.classList.add('medium');
        }
    }
    
    updateSystemStatus(status) {
        if (this.systemStatus) {
            this.systemStatus.textContent = status;
            this.systemStatus.className = `status-value ${status}`;
        }
    }
    
    animateValueChange(element, newValue) {
        if (element.textContent !== newValue) {
            element.classList.add('updating');
            element.textContent = newValue;
            setTimeout(() => {
                element.classList.remove('updating');
            }, 1000);
        }
    }

    updateValueChange(element, newValue) {
        if (element.textContent !== newValue) {
            element.textContent = newValue;
        }
    }
    
    updateLastUpdateTime(timestamp) {
        const time = timestamp ? new Date(timestamp) : new Date();
        this.lastUpdate.textContent = time.toLocaleTimeString();
    }
    
    changePumpState(state) {
        if (this.isConnected) {
            this.socket.emit('set_pump_state', { state: state });
            console.log(`Requesting pump state change to: ${state}`);
        } else {
            this.showError('Not connected to server');
        }
    }
    
    attemptReconnect() {
        console.log(`Attempting to reconnect...`);
        setTimeout(() => {
            if (!this.isConnected) {
                this.socket.connect();
            }
        }, this.reconnectDelay);
    }
    
    hideLoadingOverlay() {
        setTimeout(() => {
            this.loadingOverlay.classList.add('hidden');
        }, 500);
    }
    
    showLoadingOverlay() {
        this.loadingOverlay.classList.remove('hidden');
    }
    
    startConnectionTimeout() {
        console.log('Starting 5-minute connection timeout...');
        this.connectionTimeoutId = setTimeout(() => {
            if (!this.isConnected) {
                console.warn('Connection timeout reached (5 minutes). Reloading page...');
                this.showError('Connection timeout. Reloading page...');
                setTimeout(() => {
                    window.location.reload();
                }, 2000); // Give user 2 seconds to see the message
            }
        }, this.connectionTimeout);
    }
    
    clearConnectionTimeout() {
        if (this.connectionTimeoutId) {
            clearTimeout(this.connectionTimeoutId);
            this.connectionTimeoutId = null;
            console.log('Connection timeout cleared');
        }
    }
    
    showConnectionError() {
        this.showError('Unable to connect to dashboard server. Please check your connection.');
    }
    
    showError(message) {
        // Create a simple error notification
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #e74c3c;
            color: white;
            padding: 15px 20px;
            border-radius: 5px;
            z-index: 1001;
            max-width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
        errorDiv.textContent = message;
        
        document.body.appendChild(errorDiv);
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
    
    // Pump selection methods
    updatePumpSelection() {
        // Remove selected class from both pumps
        this.pumpControl1.classList.remove('selected-pump');
        this.pumpControl2.classList.remove('selected-pump');
        
        // Add selected class to the currently selected pump
        if (this.selectedPump === 1) {
            this.pumpControl1.classList.add('selected-pump');
        } else {
            this.pumpControl2.classList.add('selected-pump');
        }
    }
    
    toggleSelectedPump() {
        // Switch between pump 1 and pump 2
        this.selectedPump = this.selectedPump === 1 ? 2 : 1;
        this.updatePumpSelection();
        console.log(`Selected pump changed to: ${this.selectedPump}`);
        return this.selectedPump;
    }
    
    getSelectedPump() {
        return this.selectedPump;
    }
    
    setSelectedPump(pumpNumber, fromWebSocket = false) {
        if (pumpNumber === 1 || pumpNumber === 2) {
            this.selectedPump = pumpNumber;
            this.updatePumpSelection();
            console.log(`Selected pump set to: ${this.selectedPump}`);
            
            // Only emit WebSocket event if not called from WebSocket (to avoid loops)
            if (!fromWebSocket && this.isConnected) {
                this.socket.emit('pump_selection_changed', {
                    selected_pump: this.selectedPump,
                    timestamp: new Date().toISOString()
                });
            }
        } else {
            console.error('Invalid pump number. Must be 1 or 2.');
        }
        return this.selectedPump;
    }

    // Public API methods
    requestData() {
        if (this.isConnected) {
            this.socket.emit('request_data');
        }
    }
    
    getData() {
        return this.data;
    }
    
    isConnectedToServer() {
        return this.isConnected;
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'r':
                    e.preventDefault();
                    window.dashboard.requestData();
                    break;
                case 'f5':
                    e.preventDefault();
                    window.location.reload();
                    break;
            }
        }
        
        // Pump selection shortcut (P key)
        if (e.key === 'p' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault();
            window.dashboard.toggleSelectedPump();
        }
    });
    
    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && window.dashboard.isConnectedToServer()) {
            window.dashboard.requestData();
        }
    });
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboard && window.dashboard.socket) {
        window.dashboard.socket.disconnect();
    }
});
