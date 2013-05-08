(function (global) {
	function encodeUiState (uiState) {
		var json = JSON.stringify(uiState);
		if (json == "{}") {
			return null;
		}
		return json;
	}
	function decodeUiState (uiStateString) {
		if (uiStateString == "" || uiStateString == null) {
			return {};
		}
		return JSON.parse(uiStateString);
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
		Jsonary.registerSchemaChangeListener(function (data, schemas) {
			var uniqueId = data.uniqueId;
			var elementIds = thisContext.elementLookup[uniqueId];
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
				var prevUiState = decodeUiState(element.getAttribute("data-jsonary"));
				var renderer = selectRenderer(data, prevUiState, prevContext.usedComponents);
				if (renderer.uniqueId == prevContext.renderer.uniqueId) {
					renderer.render(element, data, prevContext);
				} else {
					prevContext.baseContext.render(element, data, prevContext.label, prevUiState);
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
		getSubContext: function (elementId, data, label, uiStartingState) {
			var labelKey = data.uniqueId + ":" + label;
			if (this.oldSubContexts[labelKey] != undefined) {
				this.subContexts[labelKey] = this.oldSubContexts[labelKey];
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
					this.uiState = uiState;
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
			}
		},
		render: function (element, data, label, uiStartingState) {
			if (label == undefined) {
				label = "";
			}
			// If data is a URL, then fetch it and call back
			if (typeof data == "string") {
				data = Jsonary.getData(data);
			}
			if (data.getData != undefined) {
				var thisContext = this;
				data.getData(function (actualData) {
					thisContext.render(element, actualData, label, uiStartingState);
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
			var encodedState = encodeUiState(uiStartingState);
			if (encodedState != null) {
				element.setAttribute("data-jsonary", encodedState);
			} else {
				element.removeAttribute("data-jsonary");
			}
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
				renderer.render(element, data, subContext);
				subContext.clearOldSubContexts();
			} else {
				element.innerHTML = "NO RENDERER FOUND";
			}
		},
		renderHtml: function (data, label, uiStartingState) {
			if (label == undefined) {
				label = "";
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
						thisContext.render(document.getElementById(elementId), actualData, label, uiStartingState);
					}
				});
				if (!rendered) {
					rendered = true;
					return '<span id="' + elementId + '">Loading...</span>';
				}
			}

			if (typeof uiStartingState != "object") {
				uiStartingState = {};
			}
			var subContext = this.getSubContext(elementId, data, label, uiStartingState);

			var startingStateString = encodeUiState(uiStartingState);
			var renderer = selectRenderer(data, uiStartingState, subContext.usedComponents);
			subContext.renderer = renderer;
			
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
			if (startingStateString != null) {
				return '<span id="' + elementId + '" data-jsonary=\'' + htmlEscapeSingleQuote(startingStateString) + '\'>' + innerHtml + '</span>';
			} else {
				return '<span id="' + elementId + '">' + innerHtml + '</span>';
			}
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
				var prevUiState = decodeUiState(element.getAttribute("data-jsonary"));
				var renderer = selectRenderer(data, prevUiState, prevContext.usedComponents);
				if (renderer.uniqueId == prevContext.renderer.uniqueId) {
					renderer.update(element, data, prevContext, operation);
				} else {
					prevContext.baseContext.render(element, data, prevContext.label, prevUiState);
				}
			}
		},
		actionHtml: function(innerHtml, actionName) {
			var params = [];
			for (var i = 2; i < arguments.length; i++) {
				params.push(arguments[i]);
			}
			var elementId = this.getElementId();
			this.addEnhancementAction(elementId, actionName, this, params);
			return '<a href="javascript:void(0)" id="' + elementId + '" style="text-decoration: none">' + innerHtml + '</a>';
		},
		inputNameForAction: function (actionName) {
			var params = [];
			for (var i = 1; i < arguments.length; i++) {
				params.push(arguments[i]);
			}
			var name = this.getElementId();
			this.enhancementInputs[name] = {
				inputName: name,
				actionName: actionName,
				context: this,
				params: params
			};
			return name;
		},
		addEnhancement: function(elementId, context) {
			this.enhancementContexts[elementId] = context;
		},
		addEnhancementAction: function (elementId, actionName, context, params) {
			if (params == null) {
				params = [];
			}
			this.enhancementActions[elementId] = {
				actionName: actionName,
				context: context,
				params: params
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
						var element = document.getElementById(redrawElementId);
						actionContext.renderer.render(element, actionContext.data, actionContext);
					}
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
						// Action returned positive - we should force a re-render
						var element = document.getElementById(redrawElementId);
						inputContext.renderer.render(element, inputContext.data, inputContext);
					}
				};
			}
			element = null;
		}
	};
	var pageContext = new RenderContext();

	function render(element, data, uiStartingState) {
		pageContext.render(element, data, null, uiStartingState);
		pageContext.oldSubContexts = {};
		pageContext.subContexts = {};
		return this;
	}
	function renderHtml(data, uiStartingState) {
		var result = pageContext.renderHtml(data, null, uiStartingState);
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
	}
	Renderer.prototype = {
		render: function (element, data, context) {
			if (element == null) {
				Jsonary.log(Jsonary.logLevel.ERROR, "Attempted to render to non-existent element.\n\tData path: " + data.pointerPath() + "\n\tDocument: " + data.document.url);
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
		action: function (context, actionName, data) {
			return this.actionFunction.apply(this, arguments);
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
		}
	}

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
