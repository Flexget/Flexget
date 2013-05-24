(function (global) {
	function copyValue(value) {
		return (typeof value == "object") ? JSON.parse(JSON.stringify(value)) : value;
	}
	var randomChars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
	function randomId(length) {
		length = length || 10;
		var result = "";
		while (result.length < length) {
			result += randomChars.charAt(Math.floor(Math.random()*randomChars.length));
		}
		return result;
	}

	function htmlEscapeSingleQuote (str) {
		return str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;");
	}

	var prefixPrefix = "Jsonary";
	var prefixCounter = 0;

	var componentNames = {
		ADD_REMOVE: "ADD_REMOVE",
		TYPE_SELECTOR: "TYPE_SELECTOR",
		RENDERER: "DATA_RENDERER",
		add: function (newName, beforeName) {
			if (this[newName] != undefined) {
				return;
			}
			this[newName] = newName;
			if (componentList.indexOf(beforeName) != -1) {
				componentList.splice(componentList.indexOf(beforeName), 0, this[newName]);
			} else {
				componentList.splice(componentList.length - 1, 0, this[newName]);
			}
		}
	};	
	var componentList = [componentNames.ADD_REMOVE, componentNames.TYPE_SELECTOR, componentNames.RENDERER];
	
	function RenderContext(elementIdPrefix) {
		var thisContext = this;
		this.elementLookup = {};

		if (elementIdPrefix == undefined) {
			elementIdPrefix = prefixPrefix + "." + (prefixCounter++) + ".";
		}
		var elementIdCounter = 0;
		this.getElementId = function () {
			return elementIdPrefix + (elementIdCounter++);
		};

		var renderDepth = 0;
		this.enhancementContexts = {};
		this.enhancementActions = {};
		this.enhancementInputs = {};

		Jsonary.registerChangeListener(function (patch, document) {
			patch.each(function (index, operation) {
				var dataObjects = document.affectedData(operation);
				for (var i = 0; i < dataObjects.length; i++) {
					thisContext.update(dataObjects[i], operation);
				}
			});
		});
		Jsonary.registerSchemaChangeListener(function (dataObjects) {
			var elementIdLookup = {};
			for (var i = 0; i < dataObjects.length; i++) {
				var data = dataObjects[i];
				var uniqueId = data.uniqueId;
				var elementIds = thisContext.elementLookup[uniqueId];
				if (elementIds == undefined || elementIds.length == 0) {
					return;
				}
				elementIdLookup[uniqueId] = elementIds.slice(0);
			}
			for (var j = 0; j < dataObjects.length; j++) {
				var data = dataObjects[j];
				var uniqueId = data.uniqueId;
				var elementIds = elementIdLookup[uniqueId];
				for (var i = 0; i < elementIds.length; i++) {
					var element = document.getElementById(elementIds[i]);
					if (element == undefined) {
						continue;
					}
					var prevContext = element.jsonaryContext;
					var prevUiState = copyValue(this.uiStartingState);
					var renderer = selectRenderer(data, prevUiState, prevContext.usedComponents);
					if (renderer.uniqueId == prevContext.renderer.uniqueId) {
						renderer.render(element, data, prevContext);
					} else {
						prevContext.baseContext.render(element, data, prevContext.label, prevUiState);
					}
				}
			}
		});
		this.rootContext = this;
		this.subContexts = {};
		this.oldSubContexts = {};
	}
	RenderContext.prototype = {
		usedComponents: [],
		rootContext: null,
		baseContext: null,
		subContext: function (label, uiState) {
			if (uiState == undefined) {
				uiState = {};
			}
			return this.getSubContext(this.elementId, this.data, label, uiState);
		},
		subContextSavedStates: {},
		saveState: function () {
			var subStates = {};
			for (var key in this.subContexts) {
				subStates[key] = this.subContexts[key].saveState();
			}
			for (var key in this.oldSubContexts) {
				subStates[key] = this.oldSubContexts[key].saveState();
			}
			
			var saveStateFunction = this.renderer ? this.renderer.saveState : Renderer.prototype.saveState;
			return saveStateFunction.call(this.renderer, this.uiState, subStates, this.data);
		},
		loadState: function (savedState) {
			var loadStateFunction = this.renderer ? this.renderer.loadState : Renderer.prototype.loadState;
			var result = loadStateFunction.call(this.renderer, savedState);
			this.uiState = result[0];
			this.subContextSavedStates = result[1];
		},
		getSubContext: function (elementId, data, label, uiStartingState) {
			if (typeof label == "object" && label != null) {
				throw new Error('Label cannot be an object');
			}
			if (label || label === "") {
				var labelKey = label;
			} else {
				var labelKey = data.uniqueId;
			}
			if (this.oldSubContexts[labelKey] != undefined) {
				this.subContexts[labelKey] = this.oldSubContexts[labelKey];
			}
			if (this.subContexts[labelKey] != undefined) {
				if (this.subContexts[labelKey].data != data) {
					delete this.subContexts[labelKey];
					delete this.oldSubContexts[labelKey];
					delete this.subContextSavedStates[labelKey];
				}
			}
			if (this.subContextSavedStates[labelKey]) {
				uiStartingState = this.subContextSavedStates[labelKey];
			}
			if (this.subContexts[labelKey] == undefined) {
				var usedComponents = [];
				if (this.data == data) {
					usedComponents = this.usedComponents.slice(0);
					if (this.renderer != undefined) {
						usedComponents = usedComponents.concat(this.renderer.component);
					}
				}
				if (typeof elementId == "object") {
					elementId = elementId.id;
				}
				function Context(rootContext, baseContext, label, data, uiState, usedComponents) {
					this.rootContext = rootContext;
					this.baseContext = baseContext;
					this.label = label;
					this.data = data;
					this.uiStartingState = copyValue(uiState || {});
					this.usedComponents = usedComponents;
					this.subContexts = {};
					this.oldSubContexts = {};
				}
				Context.prototype = this.rootContext;
				this.subContexts[labelKey] = new Context(this.rootContext, this, label, data, uiStartingState, usedComponents);
			}
			var subContext = this.subContexts[labelKey];
			subContext.elementId = elementId;
			return subContext;
		},
		clearOldSubContexts: function () {
			this.oldSubContexts = this.subContexts;
			this.subContexts = {};
		},
		rerender: function () {
			var element = document.getElementById(this.elementId);
			if (element != null) {
				this.renderer.render(element, this.data, this);
				this.clearOldSubContexts();
			}
		},
		render: function (element, data, label, uiStartingState, contextCallback) {
			if (uiStartingState == undefined && typeof label == "object") {
				uiStartingState = label;
				label = null;
			}
			// If data is a URL, then fetch it and call back
			if (typeof data == "string") {
				data = Jsonary.getData(data);
			}
			if (data.getData != undefined) {
				var thisContext = this;
				data.getData(function (actualData) {
					thisContext.render(element, actualData, label, uiStartingState, contextCallback);
				});
				return;
			}

			if (typeof uiStartingState != "object") {
				uiStartingState = {};
			}
			if (element.id == undefined || element.id == "") {
				element.id = this.getElementId();
			}

			var previousContext = element.jsonaryContext;
			var subContext = this.getSubContext(element.id, data, label, uiStartingState);
			element.jsonaryContext = subContext;

			if (previousContext) {
				// Something was rendered here before - remove this element from the lookup list for that data ID
				var previousId = previousContext.data.uniqueId;
				var index = this.elementLookup[previousId].indexOf(element.id);
				if (index >= 0) {
					this.elementLookup[previousId].splice(index, 1);
				}
			}
			var uniqueId = data.uniqueId;
			if (this.elementLookup[uniqueId] == undefined) {
				this.elementLookup[uniqueId] = [];
			}
			if (this.elementLookup[uniqueId].indexOf(element.id) == -1) {
				this.elementLookup[uniqueId].push(element.id);
			}
			var renderer = selectRenderer(data, uiStartingState, subContext.usedComponents);
			if (renderer != undefined) {
				subContext.renderer = renderer;
				if (subContext.uiState == undefined) {
					subContext.loadState(subContext.uiStartingState);
				}
				renderer.render(element, data, subContext);
				subContext.clearOldSubContexts();
			} else {
				element.innerHTML = "NO RENDERER FOUND";
			}
			if (contextCallback) {
				contextCallback(subContext);
			}
		},
		renderHtml: function (data, label, uiStartingState) {
			if (uiStartingState == undefined && typeof label == "object") {
				uiStartingState = label;
				label = null;
			}
			var elementId = this.getElementId();
			if (typeof data == "string") {
				data = Jsonary.getData(data);
			}
			if (data.getData != undefined) {
				var thisContext = this;
				var rendered = false;
				data.getData(function (actualData) {
					if (!rendered) {
						rendered = true;
						data = actualData;
					} else {
						var element = document.getElementById(elementId);
						element.className = "";
						if (element) {
							thisContext.render(element, actualData, label, uiStartingState);
						} else {
							Jsonary.log(Jsonary.logLevel.WARNING, "Attempted delayed render to non-existent element: " + elementId);
						}
					}
				});
				if (!rendered) {
					rendered = true;
					return '<span id="' + elementId + '" class="loading">Loading...</span>';
				}
			}
			
			if (uiStartingState === true) {
				uiStartingState = this.uiStartingState;
			}
			if (typeof uiStartingState != "object") {
				uiStartingState = {};
			}
			var subContext = this.getSubContext(elementId, data, label, uiStartingState);

			var renderer = selectRenderer(data, uiStartingState, subContext.usedComponents);
			subContext.renderer = renderer;
			if (subContext.uiState == undefined) {
				subContext.loadState(subContext.uiStartingState);
			}
			
			var innerHtml = renderer.renderHtml(data, subContext);
			subContext.clearOldSubContexts();
			var uniqueId = data.uniqueId;
			if (this.elementLookup[uniqueId] == undefined) {
				this.elementLookup[uniqueId] = [];
			}
			if (this.elementLookup[uniqueId].indexOf(elementId) == -1) {
				this.elementLookup[uniqueId].push(elementId);
			}
			this.addEnhancement(elementId, subContext);
			return '<span id="' + elementId + '">' + innerHtml + '</span>';
		},
		update: function (data, operation) {
			var uniqueId = data.uniqueId;
			var elementIds = this.elementLookup[uniqueId];
			if (elementIds == undefined || elementIds.length == 0) {
				return;
			}
			var elementIds = elementIds.slice(0);
			for (var i = 0; i < elementIds.length; i++) {
				var element = document.getElementById(elementIds[i]);
				if (element == undefined) {
					continue;
				}
				var prevContext = element.jsonaryContext;
				var prevUiState = copyValue(this.uiStartingState);
				var renderer = selectRenderer(data, prevUiState, prevContext.usedComponents);
				if (renderer.uniqueId == prevContext.renderer.uniqueId) {
					renderer.update(element, data, prevContext, operation);
				} else {
					prevContext.baseContext.render(element, data, prevContext.label, prevUiState);
				}
			}
		},
		actionHtml: function(innerHtml, actionName) {
			var startingIndex = 2;
			var historyChange = false;
			var linkUrl = "javascript:void(0)";
			if (typeof actionName == "boolean") {
				historyChange = arguments[1];
				linkUrl = arguments[2] || linkUrl;
				actionName = arguments[3];
				startingIndex += 2;
			}
			var params = [];
			for (var i = startingIndex; i < arguments.length; i++) {
				params.push(arguments[i]);
			}
			var elementId = this.getElementId();
			this.addEnhancementAction(elementId, actionName, this, params, historyChange);
			return '<a href="' + Jsonary.escapeHtml(linkUrl) + '" id="' + elementId + '" style="text-decoration: none">' + innerHtml + '</a>';
		},
		inputNameForAction: function (actionName) {
			var historyChange = false;
			var startIndex = 1;
			if (typeof actionName == "boolean") {
				historyChange = actionName;
				actionName = arguments[1];
				startIndex++;
			}
			var params = [];
			for (var i = startIndex; i < arguments.length; i++) {
				params.push(arguments[i]);
			}
			var name = this.getElementId();
			this.enhancementInputs[name] = {
				inputName: name,
				actionName: actionName,
				context: this,
				params: params,
				historyChange: historyChange
			};
			return name;
		},
		addEnhancement: function(elementId, context) {
			this.enhancementContexts[elementId] = context;
		},
		addEnhancementAction: function (elementId, actionName, context, params, historyChange) {
			if (params == null) {
				params = [];
			}
			this.enhancementActions[elementId] = {
				actionName: actionName,
				context: context,
				params: params,
				historyChange: historyChange
			};
		},
		enhanceElement: function (element) {
			var rootElement = element;
			while (element) {
				if (element.nodeType == 1) {
					this.enhanceElementSingle(element);
				}
				if (element.firstChild) {
					element = element.firstChild;
					continue;
				}
				while (!element.nextSibling && element != rootElement) {
					element = element.parentNode;
				}
				if (element == rootElement) {
					break;
				}
				element = element.nextSibling;
			}
		},
		enhanceElementSingle: function (element) {
			var elementId = element.id;
			var context = this.enhancementContexts[elementId];
			if (context != undefined) {
				element.jsonaryContext = context;
				delete this.enhancementContexts[elementId];
				var renderer = context.renderer;
				if (renderer != undefined) {
					renderer.enhance(element, context.data, context);
				}
			}
			var action = this.enhancementActions[element.id];
			if (action != undefined) {
				delete this.enhancementActions[element.id];
				element.onclick = function () {
					var redrawElementId = action.context.elementId;
					var actionContext = action.context;
					var args = [actionContext, action.actionName].concat(action.params);
					if (actionContext.renderer.action.apply(actionContext.renderer, args)) {
						// Action returned positive - we should force a re-render
						actionContext.rerender();
					}
					notifyActionHandlers(actionContext.data, actionContext, action.actionName, action.historyChange);
					return false;
				};
			}
			var inputAction = this.enhancementInputs[element.name];
			if (inputAction != undefined) {
				delete this.enhancementInputs[element.name];
				element.onchange = function () {
					var value = this.value;
					if (this.getAttribute("type") == "checkbox") {
						value = this.checked;
					}
					if (this.tagName.toLowerCase() == "select" && this.getAttribute("multiple") != null) {
						value = [];
						for (var i = 0; i < this.options.length; i++) {
							var option = this.options[i];
							if (option.selected) {
								value.push(option.value);
							}
						}						
					}
					var redrawElementId = inputAction.context.elementId;
					var inputContext = inputAction.context;
					var args = [inputContext, inputAction.actionName, value].concat(inputAction.params);
					if (inputContext.renderer.action.apply(inputContext.renderer, args)) {
						inputContext.rerender();
					}
					notifyActionHandlers(inputContext.data, inputContext, inputAction.actionName, inputAction.historyChange);
				};
			}
			element = null;
		}
	};
	var pageContext = new RenderContext();
	setInterval(function () {
		// Clean-up sweep of pageContext's element lookup
		var keysToRemove = [];
		for (var key in pageContext.elementLookup) {
			var elementIds = pageContext.elementLookup[key];
			var found = false;
			for (var i = 0; i < elementIds.length; i++) {
				var element = document.getElementById(elementIds[i]);
				if (element) {
					found = true;
					break;
				}
			}
			if (!found) {
				keysToRemove.push(key);
			}
		}
		for (var i = 0; i < keysToRemove.length; i++) {
			delete pageContext.elementLookup[keysToRemove[i]];
		}
	}, 30000); // Every 30 seconds

	function render(element, data, uiStartingState, contextCallback) {
		var context = pageContext.render(element, data, null, uiStartingState, contextCallback);
		pageContext.oldSubContexts = {};
		pageContext.subContexts = {};
		return context;
	}
	function renderHtml(data, uiStartingState, contextCallback) {
		var result = pageContext.renderHtml(data, null, uiStartingState, contextCallback);
		pageContext.oldSubContexts = {};
		pageContext.subContexts = {};
		return result;
	}

	if (global.jQuery != undefined) {
		render.empty = function (element) {
			global.jQuery(element).empty();
		};
	} else {
		render.empty = function (element) {
			element.innerHTML = "";
		};
	}
	render.Components = componentNames;
	
	/**********/

	var rendererIdCounter = 0;
	
	function Renderer(sourceObj) {
		this.renderFunction = sourceObj.render || sourceObj.enhance;
		this.renderHtmlFunction = sourceObj.renderHtml;
		this.updateFunction = sourceObj.update;
		this.filterFunction = sourceObj.filter;
		this.actionFunction = sourceObj.action;
		for (var key in sourceObj) {
			if (this[key] == undefined) {
				this[key] = sourceObj[key];
			}
		}
		this.uniqueId = rendererIdCounter++;
		this.component = (sourceObj.component != undefined) ? sourceObj.component : componentList[componentList.length - 1];
		if (typeof this.component == "string") {
			this.component = [this.component];
		}
		if (sourceObj.saveState) {
			this.saveState = sourceObj.saveState;
		}
		if (sourceObj.loadState) {
			this.loadState = sourceObj.loadState;
		}
	}
	Renderer.prototype = {
		render: function (element, data, context) {
			if (element == null) {
				Jsonary.log(Jsonary.logLevel.WARNING, "Attempted to render to non-existent element.\n\tData path: " + data.pointerPath() + "\n\tDocument: " + data.document.url);
				return this;
			}
			if (element[0] != undefined) {
				element = element[0];
			}
			render.empty(element);
			element.innerHTML = this.renderHtml(data, context);
			if (this.renderFunction != null) {
				this.renderFunction(element, data, context);
			}
			context.enhanceElement(element);
			return this;
		},
		renderHtml: function (data, context) {
			var innerHtml = "";
			if (this.renderHtmlFunction != undefined) {
				innerHtml = this.renderHtmlFunction(data, context);
			}
			return innerHtml;
		},
		enhance: function (element, data, context) {
			if (this.renderFunction != null) {
				this.renderFunction(element, data, context);
			}
			return this;
		},
		update: function (element, data, context, operation) {
			var redraw;
			if (this.updateFunction != undefined) {
				redraw = this.updateFunction(element, data, context, operation);
			} else {
				redraw = this.defaultUpdate(element, data, context, operation);
			}
			if (redraw) {
				this.render(element, data, context);
			}
			return this;
		},
		action: function (context, actionName) {
			var result = this.actionFunction.apply(this, arguments);
			return result;
		},
		canRender: function (data, schemas, uiState) {
			if (this.filterFunction != undefined) {
				return this.filterFunction(data, schemas, uiState);
			}
			return true;
		},
		defaultUpdate: function (element, data, context, operation) {
			var redraw = false;
			var checkChildren = operation.action() != "replace";
			var pointerPath = data.pointerPath();
			if (operation.subjectEquals(pointerPath) || (checkChildren && operation.subjectChild(pointerPath) !== false)) {
				redraw = true;
			} else if (operation.target() != undefined) {
				if (operation.targetEquals(pointerPath) || (checkChildren && operation.targetChild(pointerPath) !== false)) {
					redraw = true;
				}
			}
			return redraw;
		},
		saveState: function (uiState, subStates, data) {
			var result = {};
			for (key in uiState) {
				result[key] = uiState[key];
			}
			for (var label in subStates) {
				for (var subKey in subStates[label]) {
					result[label + "-" + subKey] = subStates[label][subKey];
				}
			}
			for (key in result) {
				if (Jsonary.isData(result[key])) {
					result[key] = this.saveStateData(result[key]);
				} else {
				}
			}
			return result;
		},
		saveStateData: function (data) {
			if (!data) {
				return undefined;
			}
			if (data.document.isDefinitive) {
				return "url:" + data.referenceUrl();
			}
			data.saveStateId = data.saveStateId || randomId();
			localStorage[data.saveStateId] = JSON.stringify({
				accessed: (new Date).getTime(),
				data: data.deflate()
			});
			return data.saveStateId;
		},
		loadState: function (savedState) {
			var uiState = {};
			var subStates = {};
			for (var key in savedState) {
				if (key.indexOf("-") != -1) {
					var parts = key.split('-');
					var subKey = parts.shift();
					var remainderKey = parts.join('-');
					if (!subStates[subKey]) {
						subStates[subKey] = {};
					}
					subStates[subKey][remainderKey] = savedState[key];
				} else {
					uiState[key] = this.loadStateData(savedState[key]) || savedState[key];
					if (Jsonary.isRequest(uiState[key])) {
						(function (key) {
							uiState[key].getData(function (data) {
								uiState[key] = data;
							});
						})(key);
					}
				}
			}
			return [
				uiState,
				subStates
			]
		},
		loadStateData: function (savedState) {
			if (typeof savedState == "string" && savedState.substring(0, 4) == "url:") {
				var url = savedState.substring(4);
				var data = null;
				var request = Jsonary.getData(url, function (urlData) {
					data = urlData;
				});
				return data || request;
			}
			if (!savedState) {
				return undefined;
			}
			var stored = localStorage[savedState];
			if (!stored) {
				return undefined;
			}
			stored = JSON.parse(stored);
			var data = Jsonary.inflate(stored.data);
			data.saveStateId = savedState;
			return data;
		}
	}
	Renderer.prototype.super_ = Renderer.prototype;

	var rendererLookup = {};
	var rendererList = [];
	function register(obj) {
		var renderer = new Renderer(obj);
		rendererLookup[renderer.uniqueId] = renderer;
		rendererList.push(renderer);
		return renderer;
	}
	function deregister(rendererId) {
		if (typeof rendererId == "object") {
			rendererId = rendererId.uniqueId;
		}
		delete rendererLookup[rendererId];
		for (var i = 0; i < rendererList.length; i++) {
			if (rendererList[i].uniqueId == rendererId) {
				rendererList.splice(i, 1);
				i--;
			}
		}
	}
	render.register = register;
	render.deregister = deregister;
	
	var actionHandlers = [];
	render.addActionHandler = function (callback) {
		actionHandlers.push(callback);
	};
	function notifyActionHandlers(data, context, actionName, historyChange) {
		historyChange = !!historyChange || (historyChange == undefined);
		for (var i = 0; i < actionHandlers.length; i++) {
			var callback = actionHandlers[i];
			var result = callback(data, context, actionName, historyChange);
			if (result === false) {
				break;
			}
		}
	};
	
	function lookupRenderer(rendererId) {
		return rendererLookup[rendererId];
	}

	function selectRenderer(data, uiStartingState, usedComponents) {
		var schemas = data.schemas();
		for (var j = 0; j < componentList.length; j++) {
			if (usedComponents.indexOf(componentList[j]) == -1) {
				var component = componentList[j];
				for (var i = rendererList.length - 1; i >= 0; i--) {
					var renderer = rendererList[i];
					if (renderer.component.indexOf(component) == -1) {
						continue;
					}
					if (renderer.canRender(data, schemas, uiStartingState)) {
						return renderer;
					}
				}
			}
		}
	}

	if (typeof global.jQuery != "undefined") {
		var jQueryRender = function (data, uiStartingState) {
			var element = this[0];
			if (element != undefined) {
				render(element, data, uiStartingState);
			}
			return this;
		};
		Jsonary.extendData({
			$renderTo: function (query, uiState) {
				if (typeof query == "string") {
					query = jQuery(query);
				}
				var element = query[0];
				if (element != undefined) {
					render(element, this, uiState);
				}
			}
		});
		jQueryRender.register = function (jQueryObj) {
			if (jQueryObj.render != undefined) {
				var oldRender = jQueryObj.render;
				jQueryObj.render = function (element, data) {
					var query = $(element);
					oldRender.call(this, query, data);
				}
			}
			if (jQueryObj.update != undefined) {
				var oldUpdate = jQueryObj.update;
				jQueryObj.update = function (element, data, operation) {
					var query = $(element);
					oldUpdate.call(this, query, data, operation);
				}
			}
			render.register(jQueryObj);
		};
		jQueryRender.empty = function (query) {
			query.each(function (index, element) {
				render.empty(element);
			});
		};
		jQuery.fn.extend({renderJson: jQueryRender});
		jQuery.extend({renderJson: jQueryRender});
	}

	Jsonary.extend({
		render: render,
		renderHtml: renderHtml
	});
	Jsonary.extendData({
		renderTo: function (element, uiState) {
			if (typeof element == "string") {
				element = document.getElementById(element);
			}
			render(element, this, uiState);
		}
	});
})(this);
