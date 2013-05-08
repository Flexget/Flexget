(function (Jsonary) {

	Jsonary.render.Components.add("LIST_LINKS");
	
	Jsonary.render.register({
		component: Jsonary.render.Components.LIST_LINKS,
		update: function (element, data, context, operation) {
			// We don't care about data changes - when the links change, a re-render is forced anyway.
			return false;
		},
		renderHtml: function (data, context) {
			if (!data.readOnly()) {
				return context.renderHtml(data);
			}
			var result = "";
			
			var links = data.links();
			for (var i = 0; i < links.length; i++) {
				var link = links[i];
				var html = '<span class="button link">' + Jsonary.escapeHtml(link.rel) + '</span>';
				result += context.actionHtml(html, 'follow-link', i);
			}

			if (context.uiState.submitLink != undefined) {
				var link = data.links()[context.uiState.submitLink];
				result += '<div class="prompt-outer"><div class="prompt-inner">';
				result += context.actionHtml('<div class="prompt-overlay"></div>', 'cancel');
				result += '<div class="prompt-box"><h1>' + Jsonary.escapeHtml(link.rel) + '</h1><h2>' + Jsonary.escapeHtml(link.method) + " " + Jsonary.escapeHtml(link.href) + '</h2>';
				result += '<div>' + context.renderHtml(context.submissionData) + '</div>';
				result += '</div>';
				result += '<div class="prompt-buttons">';
				result += context.actionHtml('<span class="button">Submit</span>', 'submit');
				result += context.actionHtml('<span class="button">cancel</span>', 'cancel');
				result += '</div>';
				result += '</div></div>';
			}
			
			result += context.renderHtml(data);
			return result;
		},
		action: function (context, actionName, arg1) {
			if (actionName == "follow-link") {
				var link = context.data.links()[arg1];
				if (link.method == "GET" && link.submissionSchemas.length == 0) {
					// There's no data to prompt for, and GET links are safe, so we don't put up a dialog
					link.follow();
					return false;
				}
				context.uiState.submitLink = arg1;
				if (link.method == "PUT" && link.submissionSchemas.length == 0) {
					context.submissionData = context.data.editableCopy();
				} else {
					context.submissionData = Jsonary.create().addSchema(link.submissionSchemas);
					link.submissionSchemas.createValue(function (submissionValue) {
						context.submissionData.setValue(submissionValue);
					});
				}
				return true;
			} else if (actionName == "submit") {
				var link = context.data.links()[context.uiState.submitLink];
				delete context.uiState.submitLink;
				link.follow(context.submissionData);
				return true;
			} else {
				delete context.uiState.submitLink;
				return true;
			}
		},
		filter: function () {
			return true;
		}
	});

})(Jsonary);
