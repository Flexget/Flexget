(function (Jsonary) {
	
	function TableRenderer () {
		this.columns = [];
		this.includeHeader = false;
		this.config = {
			reorderable: true,
			tableClass: "",
			addClass: "",
			addHtml: "+ add",
			removeClass: "",
			removeHtml: "X"
		};
		
	};
	TableRenderer.prototype = {
		getRowOrder: function (data, context) {
			if (context.uiState.rowOrder != undefined && context.uiState.rowOrder.length == context.data.length()) {
				return context.uiState.rowOrder;
			}
			var order = [];
			for (var i = 0; i < context.data.length(); i++) {
				order[i] = i;
			}
			var sortColumns = context.uiState.sortColumns;
			if (sortColumns == undefined) {
				return order;
			}
			var columns = this.columns;
			var sortFunction = function (aIndex, bIndex) {
				for (var i = 0; i < sortColumns.length; i++) {
					var columnIndex = sortColumns[i].index;
					var columnKey = columns[columnIndex].key;
					var aValue = data.item(aIndex).property(columnKey).value();
					var bValue = data.item(bIndex).property(columnKey).value();
					var cmp = columns[sortColumns[i].index].sortFunction(aValue, bValue);
					if (cmp != 0) {
						if (sortColumns[i].mode != "asc") {
							cmp *= -1;
						}
						return cmp;
					}
				}
				return aIndex - bIndex;
			};
			order.sort(sortFunction);
			context.uiState.rowOrder = order;
			return order;
		},
		renderHtml: function (data, context) {
			var config = this.config;
			var columns = this.columns;
			var columnCount = columns.length;
			var html = '<table class="' + this.config.tableClass + '">';
			if (this.includeHeader) {
				html += '<thead><tr>';
				if (!data.readOnly()) {
					columnCount++;
					html += '<th></th>';
				}
				for (var i = 0; i < columns.length; i++) {
					var column = columns[i];
					html += '<th>';
					if (column.sortable) {
						html += context.actionHtml(column.title, "sort", i);
					} else {
						html += column.title;
					}
					html += '</th>';
				}
				html += '</tr></thead>';
			}
			html += '<tbody>';
			var order = this.getRowOrder(data, context);
			var renderFunc = function (index, subData) {
				html += '<tr>';
				if (!data.readOnly()) {
					html += '<td class="' + config.removeClass + '">' + context.actionHtml(config.removeHtml, "remove", index) + '</td>';
				}
				for (var i = 0; i < columns.length; i++) {
					var column = columns[i];
					html += '<td>' + context.renderHtml(subData.property(column.key)) + '</td>';
				}
				html += '</tr>';
			};
			for (var i = 0; i < order.length; i++) {
				renderFunc(order[i], data.item(order[i]));
			}
			html += '</tbody>';
			if (!data.readOnly()) {
				html += '<tfoot><tr><td class="' + this.config.addClass + '" colspan=' + columnCount + '>';
				html += context.actionHtml(config.addHtml, "append");

			html += '</td></tr></tfoot>';
			}
			html += '</table>';
			return html;
		},
		action: function (context, actionName, arg1) {
			if (actionName == "append") {
				var data = context.data;
				var index = data.length();
				if (context.uiState.rowOrder != undefined) {
					context.uiState.rowOrder[index] = index;
				}
				data.schemas().createValueForIndex(index, function (newValue) {
					data.index(index).setValue(newValue);
				});
			} else if (actionName == "remove") {
				var index = arg1;
				if (context.uiState.rowOrder != undefined) {
					var newRowOrder = [];
					for (var i = 0; i < context.uiState.rowOrder.length; i++) {
						var orderIndex = context.uiState.rowOrder[i];
						if (orderIndex < index) {
							newRowOrder.push(orderIndex);
						} else if (orderIndex > index) {
							newRowOrder.push(orderIndex - 1);
						}
					}
					context.uiState.rowOrder = newRowOrder;
				}
				context.data.item(index).remove();
			} else if (actionName == "clearSort") {
				uiState.sortColumns = [];
				return true;
			} else if (actionName == "sort") {
				var uiState = context.uiState;
				var index = arg1;
				var data = context.data;
				if (uiState.sortColumns == undefined) {
					uiState.sortColumns = [];
				}
				if (uiState.sortColumns.length > 0 && uiState.sortColumns[0].index == index) {
					uiState.sortColumns[0].mode = (uiState.sortColumns[0].mode == "asc") ? "desc" : "asc";
				} else {
					uiState.sortColumns.unshift({index: index, mode: "asc"});
				}
				for (var i = 1; i < uiState.sortColumns.length; i++) {
					if (uiState.sortColumns[i].index == index) {
						uiState.sortColumns.splice(i, 1);
						i--;
					}
				}
				delete context.uiState.rowOrder;
				return true;
			} else {
				alert("Unknown action: " + actionName);
			}
		},
		addColumn: function (key, title, sortFunction) {
			if (title != null && title != "") {
				this.includeHeader = true;
			}
			var sortable = (sortFunction != null);
			if (sortFunction === true) {
				sortFunction = this.nativeSort;
			}
			this.columns.push({key: key, title: title, sortable: sortable, sortFunction: sortFunction});
		},
		update: function (element, data, context, operation) {
			if (operation.depthFrom(data.pointerPath()) <= 2) {
				this.render(element, data, context);
			}
		},
		nativeSort: function (a, b) {
			if (a > b) {
				return 1;
			} else if (a < b) {
				return -1;
			}
			return 0;
		}
	};

	Jsonary.extend({
		TableRenderer: TableRenderer
	});
})(Jsonary);
