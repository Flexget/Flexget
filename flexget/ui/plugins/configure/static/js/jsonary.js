/**
Copyright (C) 2012 Geraint Luff

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
**/

if (typeof localStorage == "undefined") {
	window.localStorage = {};
}

// This is not a full ES5 shim - it just covers the functions that Jsonary uses.

if (!Array.isArray) {
	Array.isArray = function (candidate) {
		return Object.prototype.toString.apply(candidate) === '[object Array]';
	};
}
if (!Array.prototype.indexOf) {
	Array.prototype.indexOf = function (value, start) {
		for (var i = start || 0; i < this.length; i++) {
			if (this[i] === value) {
				return i;
			}
		}
		return -1;
	};
}
if (!Object.keys) {
	Object.keys = function (obj) {
		var result = [];
		for (var key in obj) {
			if (obj.hasOwnProperty(key)) {
				result.push(key);
			}
		}
		return result;
	};
}
if (!String.prototype.trim) {
	String.prototype.trim = function () {
		return this.replace(/^\s+|\s+$/g,'');
	};
}

// json2.js, from Douglas Crockford's GitHub repo

/*
    json2.js
    2012-10-08

    Public Domain.

    NO WARRANTY EXPRESSED OR IMPLIED. USE AT YOUR OWN RISK.

    See http://www.JSON.org/js.html


    This code should be minified before deployment.
    See http://javascript.crockford.com/jsmin.html

    USE YOUR OWN COPY. IT IS EXTREMELY UNWISE TO LOAD CODE FROM SERVERS YOU DO
    NOT CONTROL.


    This file creates a global JSON object containing two methods: stringify
    and parse.

        JSON.stringify(value, replacer, space)
            value       any JavaScript value, usually an object or array.

            replacer    an optional parameter that determines how object
                        values are stringified for objects. It can be a
                        function or an array of strings.

            space       an optional parameter that specifies the indentation
                        of nested structures. If it is omitted, the text will
                        be packed without extra whitespace. If it is a number,
                        it will specify the number of spaces to indent at each
                        level. If it is a string (such as '\t' or '&nbsp;'),
                        it contains the characters used to indent at each level.

            This method produces a JSON text from a JavaScript value.

            When an object value is found, if the object contains a toJSON
            method, its toJSON method will be called and the result will be
            stringified. A toJSON method does not serialize: it returns the
            value represented by the name/value pair that should be serialized,
            or undefined if nothing should be serialized. The toJSON method
            will be passed the key associated with the value, and this will be
            bound to the value

            For example, this would serialize Dates as ISO strings.

                Date.prototype.toJSON = function (key) {
                    function f(n) {
                        // Format integers to have at least two digits.
                        return n < 10 ? '0' + n : n;
                    }

                    return this.getUTCFullYear()   + '-' +
                         f(this.getUTCMonth() + 1) + '-' +
                         f(this.getUTCDate())      + 'T' +
                         f(this.getUTCHours())     + ':' +
                         f(this.getUTCMinutes())   + ':' +
                         f(this.getUTCSeconds())   + 'Z';
                };

            You can provide an optional replacer method. It will be passed the
            key and value of each member, with this bound to the containing
            object. The value that is returned from your method will be
            serialized. If your method returns undefined, then the member will
            be excluded from the serialization.

            If the replacer parameter is an array of strings, then it will be
            used to select the members to be serialized. It filters the results
            such that only members with keys listed in the replacer array are
            stringified.

            Values that do not have JSON representations, such as undefined or
            functions, will not be serialized. Such values in objects will be
            dropped; in arrays they will be replaced with null. You can use
            a replacer function to replace those with JSON values.
            JSON.stringify(undefined) returns undefined.

            The optional space parameter produces a stringification of the
            value that is filled with line breaks and indentation to make it
            easier to read.

            If the space parameter is a non-empty string, then that string will
            be used for indentation. If the space parameter is a number, then
            the indentation will be that many spaces.

            Example:

            text = JSON.stringify(['e', {pluribus: 'unum'}]);
            // text is '["e",{"pluribus":"unum"}]'


            text = JSON.stringify(['e', {pluribus: 'unum'}], null, '\t');
            // text is '[\n\t"e",\n\t{\n\t\t"pluribus": "unum"\n\t}\n]'

            text = JSON.stringify([new Date()], function (key, value) {
                return this[key] instanceof Date ?
                    'Date(' + this[key] + ')' : value;
            });
            // text is '["Date(---current time---)"]'


        JSON.parse(text, reviver)
            This method parses a JSON text to produce an object or array.
            It can throw a SyntaxError exception.

            The optional reviver parameter is a function that can filter and
            transform the results. It receives each of the keys and values,
            and its return value is used instead of the original value.
            If it returns what it received, then the structure is not modified.
            If it returns undefined then the member is deleted.

            Example:

            // Parse the text. Values that look like ISO date strings will
            // be converted to Date objects.

            myData = JSON.parse(text, function (key, value) {
                var a;
                if (typeof value === 'string') {
                    a =
/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2}(?:\.\d*)?)Z$/.exec(value);
                    if (a) {
                        return new Date(Date.UTC(+a[1], +a[2] - 1, +a[3], +a[4],
                            +a[5], +a[6]));
                    }
                }
                return value;
            });

            myData = JSON.parse('["Date(09/09/2001)"]', function (key, value) {
                var d;
                if (typeof value === 'string' &&
                        value.slice(0, 5) === 'Date(' &&
                        value.slice(-1) === ')') {
                    d = new Date(value.slice(5, -1));
                    if (d) {
                        return d;
                    }
                }
                return value;
            });


    This is a reference implementation. You are free to copy, modify, or
    redistribute.
*/

// Create a JSON object only if one does not already exist. We create the
// methods in a closure to avoid creating global variables.

if (typeof JSON !== 'object') {
    JSON = {};
}

(function () {
    'use strict';

    function f(n) {
        // Format integers to have at least two digits.
        return n < 10 ? '0' + n : n;
    }

    if (typeof Date.prototype.toJSON !== 'function') {

        Date.prototype.toJSON = function (key) {

            return isFinite(this.valueOf())
                ? this.getUTCFullYear()     + '-' +
                    f(this.getUTCMonth() + 1) + '-' +
                    f(this.getUTCDate())      + 'T' +
                    f(this.getUTCHours())     + ':' +
                    f(this.getUTCMinutes())   + ':' +
                    f(this.getUTCSeconds())   + 'Z'
                : null;
        };

        String.prototype.toJSON      =
            Number.prototype.toJSON  =
            Boolean.prototype.toJSON = function (key) {
                return this.valueOf();
            };
    }

    var cx = /[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,
        escapable = /[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,
        gap,
        indent,
        meta = {    // table of character substitutions
            '\b': '\\b',
            '\t': '\\t',
            '\n': '\\n',
            '\f': '\\f',
            '\r': '\\r',
            '"' : '\\"',
            '\\': '\\\\'
        },
        rep;


    function quote(string) {

// If the string contains no control characters, no quote characters, and no
// backslash characters, then we can safely slap some quotes around it.
// Otherwise we must also replace the offending characters with safe escape
// sequences.

        escapable.lastIndex = 0;
        return escapable.test(string) ? '"' + string.replace(escapable, function (a) {
            var c = meta[a];
            return typeof c === 'string'
                ? c
                : '\\u' + ('0000' + a.charCodeAt(0).toString(16)).slice(-4);
        }) + '"' : '"' + string + '"';
    }


    function str(key, holder) {

// Produce a string from holder[key].

        var i,          // The loop counter.
            k,          // The member key.
            v,          // The member value.
            length,
            mind = gap,
            partial,
            value = holder[key];

// If the value has a toJSON method, call it to obtain a replacement value.

        if (value && typeof value === 'object' &&
                typeof value.toJSON === 'function') {
            value = value.toJSON(key);
        }

// If we were called with a replacer function, then call the replacer to
// obtain a replacement value.

        if (typeof rep === 'function') {
            value = rep.call(holder, key, value);
        }

// What happens next depends on the value's type.

        switch (typeof value) {
        case 'string':
            return quote(value);

        case 'number':

// JSON numbers must be finite. Encode non-finite numbers as null.

            return isFinite(value) ? String(value) : 'null';

        case 'boolean':
        case 'null':

// If the value is a boolean or null, convert it to a string. Note:
// typeof null does not produce 'null'. The case is included here in
// the remote chance that this gets fixed someday.

            return String(value);

// If the type is 'object', we might be dealing with an object or an array or
// null.

        case 'object':

// Due to a specification blunder in ECMAScript, typeof null is 'object',
// so watch out for that case.

            if (!value) {
                return 'null';
            }

// Make an array to hold the partial results of stringifying this object value.

            gap += indent;
            partial = [];

// Is the value an array?

            if (Object.prototype.toString.apply(value) === '[object Array]') {

// The value is an array. Stringify every element. Use null as a placeholder
// for non-JSON values.

                length = value.length;
                for (i = 0; i < length; i += 1) {
                    partial[i] = str(i, value) || 'null';
                }

// Join all of the elements together, separated with commas, and wrap them in
// brackets.

                v = partial.length === 0
                    ? '[]'
                    : gap
                    ? '[\n' + gap + partial.join(',\n' + gap) + '\n' + mind + ']'
                    : '[' + partial.join(',') + ']';
                gap = mind;
                return v;
            }

// If the replacer is an array, use it to select the members to be stringified.

            if (rep && typeof rep === 'object') {
                length = rep.length;
                for (i = 0; i < length; i += 1) {
                    if (typeof rep[i] === 'string') {
                        k = rep[i];
                        v = str(k, value);
                        if (v) {
                            partial.push(quote(k) + (gap ? ': ' : ':') + v);
                        }
                    }
                }
            } else {

// Otherwise, iterate through all of the keys in the object.

                for (k in value) {
                    if (Object.prototype.hasOwnProperty.call(value, k)) {
                        v = str(k, value);
                        if (v) {
                            partial.push(quote(k) + (gap ? ': ' : ':') + v);
                        }
                    }
                }
            }

// Join all of the member texts together, separated with commas,
// and wrap them in braces.

            v = partial.length === 0
                ? '{}'
                : gap
                ? '{\n' + gap + partial.join(',\n' + gap) + '\n' + mind + '}'
                : '{' + partial.join(',') + '}';
            gap = mind;
            return v;
        }
    }

// If the JSON object does not yet have a stringify method, give it one.

    if (typeof JSON.stringify !== 'function') {
        JSON.stringify = function (value, replacer, space) {

// The stringify method takes a value and an optional replacer, and an optional
// space parameter, and returns a JSON text. The replacer can be a function
// that can replace values, or an array of strings that will select the keys.
// A default replacer method can be provided. Use of the space parameter can
// produce text that is more easily readable.

            var i;
            gap = '';
            indent = '';

// If the space parameter is a number, make an indent string containing that
// many spaces.

            if (typeof space === 'number') {
                for (i = 0; i < space; i += 1) {
                    indent += ' ';
                }

// If the space parameter is a string, it will be used as the indent string.

            } else if (typeof space === 'string') {
                indent = space;
            }

// If there is a replacer, it must be a function or an array.
// Otherwise, throw an error.

            rep = replacer;
            if (replacer && typeof replacer !== 'function' &&
                    (typeof replacer !== 'object' ||
                    typeof replacer.length !== 'number')) {
                throw new Error('JSON.stringify');
            }

// Make a fake root object containing our value under the key of ''.
// Return the result of stringifying the value.

            return str('', {'': value});
        };
    }


// If the JSON object does not yet have a parse method, give it one.

    if (typeof JSON.parse !== 'function') {
        JSON.parse = function (text, reviver) {

// The parse method takes a text and an optional reviver function, and returns
// a JavaScript value if the text is a valid JSON text.

            var j;

            function walk(holder, key) {

// The walk method is used to recursively walk the resulting structure so
// that modifications can be made.

                var k, v, value = holder[key];
                if (value && typeof value === 'object') {
                    for (k in value) {
                        if (Object.prototype.hasOwnProperty.call(value, k)) {
                            v = walk(value, k);
                            if (v !== undefined) {
                                value[k] = v;
                            } else {
                                delete value[k];
                            }
                        }
                    }
                }
                return reviver.call(holder, key, value);
            }


// Parsing happens in four stages. In the first stage, we replace certain
// Unicode characters with escape sequences. JavaScript handles many characters
// incorrectly, either silently deleting them, or treating them as line endings.

            text = String(text);
            cx.lastIndex = 0;
            if (cx.test(text)) {
                text = text.replace(cx, function (a) {
                    return '\\u' +
                        ('0000' + a.charCodeAt(0).toString(16)).slice(-4);
                });
            }

// In the second stage, we run the text against regular expressions that look
// for non-JSON patterns. We are especially concerned with '()' and 'new'
// because they can cause invocation, and '=' because it can cause mutation.
// But just to be safe, we want to reject all unexpected forms.

// We split the second stage into 4 regexp operations in order to work around
// crippling inefficiencies in IE's and Safari's regexp engines. First we
// replace the JSON backslash pairs with '@' (a non-JSON character). Second, we
// replace all simple value tokens with ']' characters. Third, we delete all
// open brackets that follow a colon or comma or that begin the text. Finally,
// we look to see that the remaining characters are only whitespace or ']' or
// ',' or ':' or '{' or '}'. If that is so, then the text is safe for eval.

            if (/^[\],:{}\s]*$/
                    .test(text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, '@')
                        .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, ']')
                        .replace(/(?:^|:|,)(?:\s*\[)+/g, ''))) {

// In the third stage we use the eval function to compile the text into a
// JavaScript structure. The '{' operator is subject to a syntactic ambiguity
// in JavaScript: it can begin a block or an object literal. We wrap the text
// in parens to eliminate the ambiguity.

                j = eval('(' + text + ')');

// In the optional fourth stage, we recursively walk the new structure, passing
// each name/value pair to a reviver function for possible transformation.

                return typeof reviver === 'function'
                    ? walk({'': j}, '')
                    : j;
            }

// If the text is not JSON parseable, then a SyntaxError is thrown.

            throw new SyntaxError('JSON.parse');
        };
    }
}());

(function(global) { // Global wrapper
	
var publicApi = {
    "toString": function() {
        return "[JsonApi]";
    }
};
global.Jsonary = publicApi;

function setTimeout(fn, t) {
	throw new Error("setTimeout() should not be used");
}


function Uri(str) {
	var scheme = str.match(/^[a-zA-Z\-]+:/);
	if (scheme != null && scheme.length > 0) {
		this.scheme = scheme[0].substring(0, scheme[0].length - 1);
		str = str.substring(scheme[0].length);
	} else {
		this.scheme = null;
	}
	
	if (str.substring(0, 2) == "//") {
		this.doubleSlash = true;
		str = str.substring(2);
	} else {
		this.doubleSlash = false;
	}

	var hashIndex = str.indexOf("#");
	if (hashIndex >= 0) {
		var fragmentString = str.substring(hashIndex + 1);
		this.fragment = unpackFragment(fragmentString);
		str = str.substring(0, hashIndex);
	} else {
		this.hash = null;
	}
	
	var queryIndex = str.indexOf("?");
	if (queryIndex >= 0) {
		var queryString = str.substring(queryIndex + 1);
		this.query = unpackQuery(queryString);
		str = str.substring(0, queryIndex);
	} else {
		this.query = null;
	}
	
	var atIndex = str.indexOf("@");
	if (atIndex >= 0) {
		var userCredentials = str.substring(0, atIndex);
		var colonIndex = userCredentials.indexOf(":");
		if (colonIndex == -1) {
			this.username = userCredentials;
			this.password = null;
		} else {
			this.username = userCredentials.substring(0, colonIndex);
			this.password = userCredentials.substring(colonIndex + 1);
		}
		var str = str.substring(atIndex + 1);
	} else {
		this.username = null;
		this.password = null;
	}

	var slashIndex = 0;
	if (this.scheme != null || this.doubleSlash) {
		slashIndex = str.indexOf("/");
	}
	if (slashIndex >= 0) {
		this.path = str.substring(slashIndex);
		if (this.path == "") {
			this.path = null;
		}
		str = str.substring(0, slashIndex);
	} else {
		this.path = null;
	}
	
	var colonIndex = str.indexOf(":");
	if (colonIndex >= 0) {
		this.port = str.substring(colonIndex + 1);
		str = str.substring(0, colonIndex);
	} else {
		this.port = null;
	}
	
	if (str == "") {
		this.domain = null;
	} else {
		this.domain = str;
	}
}
Uri.prototype = {
	toString: function() {
		var result = "";
		if (this.scheme != null) {
			result += this.scheme + ":";
		}
		if (this.doubleSlash) {
			result += "//";
		}
		if (this.username != null) {
			result += this.username;
			if (this.password != null) {
				result += ":" + this.password;
			}
			result += "@";
		}
		if (this.domain != null) {
			result += this.domain;
		}
		if (this.port != null) {
			result += ":" + this.port;
		}
		if (this.path != null) {
			result += this.path;
		}
		if (this.query != null) {
			result += "?" + this.query;
		}
		if (this.fragment != null) {
			result += "#" + this.fragment;
		}
		return result;
	}
};
Uri.resolve = function(base, relative) {
	if (relative == undefined) {
		return base;
		//  We used to resolve relative to window.location, but we want to be able to run outside the browser as well
		//relative = base;
		//base = window.location.toString();
	}
	if (base == undefined) {
		return relative;
	}
	if (!(base instanceof Uri)) {
		base = new Uri(base);
	}
	result = new Uri(relative + "");
	if (result.scheme == null) {
		result.scheme = base.scheme;
		result.doubleSlash = base.doubleSlash;
		if (result.domain == null) {
			result.domain = base.domain;
			result.port = base.port;
			result.username = base.username;
			result.password = base.password;
			if (result.path == null) {
				result.path = base.path;
				if (result.query == null) {
					result.query = base.query;
				}
			} else if (result.path.charAt(0) != "/" && base.path != null) {
				var precedingSlash = base.path.charAt(0) == "/";
				var baseParts;
				if (precedingSlash) {
					baseParts = base.path.substring(1).split("/");
				} else {
					baseParts = base.path.split("/");
				}
				if (baseParts[baseParts.length - 1] == "..") {
					baseParts.push("");
				}
				baseParts.pop();
				for (var i = baseParts.length - 1; i >= 0; i--) {
					if (baseParts[i] == ".") {
						baseParts.slice(i, 1);
					}
				}
				var resultParts = result.path.split("/");
				for (var i = 0; i < resultParts.length; i++) {
					var part = resultParts[i];
					if (part == ".") {
						continue;
					} else if (part == "..") {
						if (baseParts.length > 0 && baseParts[baseParts.length - 1] != "..") {
							baseParts.pop();
						} else if (!precedingSlash) {
							baseParts = baseParts.concat(resultParts.slice(i));
							break;
						}
					} else {
						baseParts.push(part);
					}
				}
				result.path = (precedingSlash ? "/" : "") + baseParts.join("/");
			}
		}
	}
	return result.toString();
};
Uri.parse = function(uri) {
	return new Uri(uri);
}

function unpackQuery(queryString) {
	var parts = queryString.split("&");
	var pairs = [];
	for (var i = 0; i < parts.length; i++) {
		var part = parts[i];
		var index = part.indexOf("=");
		if (index == -1) {
			pairs.push({key: part});
		} else {
			var key = part.substring(0, index);
			var value = part.substring(index + 1);
			pairs.push({key:key, value:decodeURIComponent(value)});
		}
	}
	for (var key in queryFunctions) {
		pairs[key] = queryFunctions[key];
	}
	pairs.isQuery = true;
	return pairs;
};
function unpackFragment(fragmentString) {
	if (fragmentString.indexOf("?") != -1) {
		fragmentString.isQuery = false;
	} else {
		return unpackQuery(fragmentString);
	}
}
var queryFunctions = {
	toString: function() {
		var result = [];
		for (var i = 0; i < this.length; i++) {
			if (typeof this[i].value == "undefined") {
				result.push(this[i].key);
			} else {
				result.push(this[i].key + "=" + encodeURIComponent(this[i].value));
			}
		}
		return result.join("&");
	},
	get: function(key, defaultValue) {
		for (var i = 0; i < this.length; i++) {
			if (this[i].key == key) {
				return this[i].value;
			}
		}
		return defaultValue;
	},
	set: function(key, value) {
		for (var i = 0; i < this.length; i++) {
			if (this[i].key == key) {
				this[i].value = value;
				return;
			}
		}
		this.push({key: key, value: value});
	}
};

publicApi.Uri = Uri;

var uriTemplateGlobalModifiers = {
	"+": true,
	"#": true,
	".": true,
	"/": true,
	";": true,
	"?": true,
	"&": true
};
var uriTemplateSuffices = {
	"*": true
};

function uriTemplateSubstitution(spec) {
	var modifier = "";
	if (uriTemplateGlobalModifiers[spec.charAt(0)]) {
		modifier = spec.charAt(0);
		spec = spec.substring(1);
	}
	var separator = ",";
	var prefix = "";
	var shouldEscape = true;
	var showVariables = false;
	if (modifier == '+') {
		shouldEscape = false;
	} else if (modifier == ".") {
		prefix = ".";
		separator = ".";
	} else if (modifier == "/") {
		prefix = "/";
		separator = "/";
	} else if (modifier == '#') {
		prefix = "#";
		shouldEscape = false;
	} else if (modifier == ';') {
		prefix = ";";
		separator = ";",
		showVariables = true;
	} else if (modifier == '?') {
		prefix = "?";
		separator = "&",
		showVariables = true;
	} else if (modifier == '&') {
		prefix = "&";
		separator = "&",
		showVariables = true;
	}

	var varNames = [];
	var varList = spec.split(",");
	var varSpecs = [];
	for (var i = 0; i < varList.length; i++) {
		var varSpec = varList[i];
		var truncate = null;
		if (varSpec.indexOf(":") != -1) {
			var parts = varSpec.split(":");
			varSpec = parts[0];
			truncate = parseInt(parts[1]);
		}
		var suffices = {};
		while (uriTemplateSuffices[varSpec.charAt(varSpec.length - 1)]) {
			suffices[varSpec.charAt(varSpec.length - 1)] = true;
			varSpec = varSpec.substring(0, varSpec.length - 1);
		}
		varSpecs.push({
			truncate: truncate,
			name: varSpec,
			suffices: suffices
		});
		varNames.push(varSpec);
	}
	var resultFunction = function (valueFunction) {
		var result = prefix;
		for (var i = 0; i < varSpecs.length; i++) {
			var varSpec = varSpecs[i];
			if (i > 0) {
				result += separator;
			}
			var value = valueFunction(varSpec.name);
			if (Array.isArray(value)) {
				if (showVariables) {
					result += varSpec.name + "=";
				}
				for (var j = 0; j < value.length; j++) {
					if (j > 0) {
						result += varSpec.suffices['*'] ? separator : ",";
						if (varSpec.suffices['*'] && showVariables) {
							result += varSpec.name + "=";
						}
					}
					result += shouldEscape ? encodeURIComponent(value[j]).replace("!", "%21"): encodeURI(value[j]).replace("%25", "%");
				}
			} else if (typeof value == "object") {
				if (showVariables && !varSpec.suffices['*']) {
					result += varSpec.name + "=";
				}
				var first = true;
				for (var key in value) {
					if (!first) {
						result += varSpec.suffices['*'] ? separator : ",";
					}
					first = false;
					result += shouldEscape ? encodeURIComponent(key).replace("!", "%21"): encodeURI(key).replace("%25", "%");
					result += varSpec.suffices['*'] ? '=' : ",";
					result += shouldEscape ? encodeURIComponent(value[key]).replace("!", "%21"): encodeURI(value[key]).replace("%25", "%");
				}
			} else {
				if (showVariables) {
					result += varSpec.name + "=";
				}
				if (varSpec.truncate != null) {
					value = value.substring(0, varSpec.truncate);
				}
				result += shouldEscape ? encodeURIComponent(value).replace("!", "%21"): encodeURI(value).replace("%25", "%");
			}
		}
		return result;
	};
	resultFunction.varNames = varNames;
	return resultFunction;
}

function UriTemplate(template) {
	var parts = template.split("{");
	var textParts = [parts.shift()];
	var substitutions = [];
	var varNames = [];
	while (parts.length > 0) {
		var part = parts.shift();
		var spec = part.split("}")[0];
		var remainder = part.substring(spec.length + 1);
		var substitution = uriTemplateSubstitution(spec);
		substitutions.push(substitution);
		textParts.push(remainder);
		varNames = varNames.concat(substitution.varNames);
	}
	this.fill = function (valueFunction) {
		var result = textParts[0];
		for (var i = 0; i < substitutions.length; i++) {
			var substitution = substitutions[i];
			result += substitution(valueFunction);
			result += textParts[i + 1];
		}
		return result;
	};
	this.varNames = varNames;
}
var Utils = {
	guessBasicType: function (data, prevType) {
		if (data === null) {
			return "null";
		} else if (Array.isArray(data)) {
			return "array";
		} else if (typeof data == "object") {
			return "object";
		} else if (typeof data == "string") {
			return "string";
		} else if (typeof data == "number") {
			if (data % 1 == 0) { // we used to persist "number" if the previous type was "number", but that caused problems for no real benefit.
				return "integer";
			} else {
				return "number";
			}
		} else if (typeof data == "boolean") {
			return "boolean";
		} else {
			return undefined;
		}
	},
	resolveRelativeUri: function (baseUrl, relativeUrl) {
		return Uri.resolve(baseUrl, relativeUrl);
	},
	urlsEqual: function (url1, url2) {
		//TODO:  better URL comparison
		if (url1.charAt(url1.length - 1) == '#') {
			url1 = url1.substring(0, url1.length - 1);
		}
		if (url2.charAt(url2.length - 1) == '#') {
			url2 = url2.substring(0, url2.length - 1);
		}
		return url1 == url2;
	},
	linksEqual: function (linkList1, linkList2) {
		if (linkList1 == undefined || linkList2 == undefined) {
			return linkList1 == linkList2;
		}
		if (linkList1.length != linkList2.length) {
			return false;
		}
		for (var i = 0; i < linkList1.length; i++) {
			var link1 = linkList1[i];
			var link2 = linkList2[i];
			if (link1.href != link2.href || link1.rel != link2.rel) {
				return false;
			}
			if (link1.method != link2.method || link1['enc-type'] != link2['enc-type']) {
				return false;
			}
			if (link1.schema != link2.schema) {
				return false;
			}
		}
		return true;
	},
	log: function (level, message) {
		try {
			if (level >= Utils.logLevel.ERROR) {
				window.alert("ERROR: " + message);
				console.log("ERROR: " + message);
				console.trace();
			}
			if (level >= Utils.logLevel.WARNING) {
				console.log("WARNING: " + message);
			}
		} catch (e) {}
	},
	logLevel: {
		DEBUG: -1,
		STANDARD: 0,
		WARNING: 1,
		ERROR: 2
	},
	getKeyVariant: function (baseKey, variantName) {
		if (variantName == undefined) {
			variantName = Utils.getUniqueKey();
		}
		variantName += "";
		if (variantName.indexOf('.') >= 0) {
			throw new Error("variant name cannot contain a dot: " + variantName);
		}
		return baseKey + "." + variantName;
	},
	keyIsVariant: function (key, baseKey) {
		key += "";
		baseKey += "";
		return key === baseKey || key.substring(0, baseKey.length + 1) === (baseKey + ".");
	},
	keyIsRoot: function (key) {
		return (key.indexOf(".") == -1);
	},
	hcf: function(a, b) {
		a = Math.abs(a);
		b = Math.abs(b);
		while (true) {
			var newB = a % b;
			if (newB == 0) {
				return b;
			} else if (isNaN(newB)) {
				return NaN;
			}
			a = b;
			b = newB;
		}
	},
	recursiveCompare: function(a, b) {
		if (Array.isArray(a)) {
			if (!Array.isArray(b) || a.length != b.length) {
				return false;
			}
			for (var i = 0; i < a.length; i++) {
				if (!Utils.recursiveCompare(a[i], b[i])) {
					return false;
				}
			}
			return true;
		} else if (typeof a == "object") {
			for (var key in a) {
				if (b[key] === undefined && a[key] !== undefined) {
					return false;
				}
			}
			for (var key in b) {
				if (a[key] === undefined && a[key] !== undefined) {
					return false;
				}
			}
			for (var key in a) {
				if (!Utils.recursiveCompare(a[key], b[key])) {
					return false;
				}
			}
			return true;
		}
		return a === b;
	},
	lcm: function(a, b) {
		return Math.abs(a*b/this.hcf(a, b));
	},
	encodeData: function (data, encType) {
		if (encType == undefined) {
			encType = "application/x-www-form-urlencoded";
		}
		if (encType == "application/json") {
			return JSON.stringify(data);
		} else if (encType == "application/x-www-form-urlencoded") {
			return Utils.formEncode(data);
		} else {
			throw new Error("Unknown encoding type: " + this.encType);
		}
	},
	decodeData: function (data, encType) {
		if (encType == undefined) {
			encType = "application/x-www-form-urlencoded";
		}
		if (encType == "application/json") {
			return JSON.parse(data);
		} else if (encType == "application/x-www-form-urlencoded") {
			return Utils.formDecode(data);
		} else {
			throw new Error("Unknown encoding type: " + this.encType);
		}
	},
	formEncode: function (data, prefix) {
		if (prefix == undefined) {
			prefix = "";
		}
		var result = [];
		if (Array.isArray(data)) {
			for (var i = 0; i < data.length; i++) {
				var key = (prefix == "") ? i : prefix + encodeURIComponent("[]");
				var complexKey = (prefix == "") ? i : prefix + encodeURIComponent("[" + i + "]");
				var value = data[i];
				if (value == null) {
					result.push(key + "=null");
				} else if (typeof value == "object") {
					result.push(Utils.formEncode(value, complexKey));
				} else if (typeof value == "boolean") {
					if (value) {
						result.push(key + "=true");
					} else {
						result.push(key + "=false");
					}
				} else {
					result.push(key + "=" + encodeURIComponent(value));
				}
			}
		} else if (typeof data == "object") {
			for (var key in data) {
				if (!data.hasOwnProperty(key)) {
					continue;
				}
				var value = data[key];
				if (prefix != "") {
					key = prefix + encodeURIComponent("[" + key + "]");
				}
				if (value == "null") {
					result.push(key + "=null");
				} else if (typeof value == "object") {
					result.push(Utils.formEncode(value, key));
				} else if (typeof value == "boolean") {
					if (value) {
						result.push(key + "=true");
					} else {
						result.push(key + "=false");
					}
				} else {
					result.push(key + "=" + encodeURIComponent(value));
				}
			}
		} else {
			result.push(encodeURIComponent(data));
		}
		return result.join("&");
	},
	formDecode: function (data) {
		var result = {};
		var parts = data.split("&");
		for (var partIndex = 0; partIndex < parts.length; partIndex++) {
			var part = parts[partIndex];
			var key = part;
			var value = "";
			if (part.indexOf("=") >= 0) {
				key = part.substring(0, part.indexOf("="));
				value = decodeURIComponent(part.substring(part.indexOf("=") + 1));
				if (value == "true") {
					value = true;
				} else if (value == "false") {
					value = false;
				} else if (value == "null") {
					value = null;
				} else if (parseFloat(value) + "" == value) {
					value = parseFloat(value);
				}
			}
			key = decodeURIComponent(key);
			var subject = result;
			var keyparts = key.split("[");
			for (var i = 1; i < keyparts.length; i++) {
				keyparts[i] = keyparts[i].substring(0, keyparts[i].length - 1);
			}
			for (var i = 0; i < keyparts.length; i++) {
				if (Array.isArray(subject) && keyparts[i] == "") {
					keyparts[i] = subject.length;
				}
				if (i == keyparts.length - 1) {
					subject[keyparts[i]] = value;
				} else {
					if (subject[keyparts[i]] == undefined) {
						if (keyparts[i + 1] == "") {
							subject[keyparts[i]] = [];
						} else {
							subject[keyparts[i]] = {};
						}
					}
					subject = subject[keyparts[i]];
				}
			}
		}
		return result;
	},
	escapeHtml: function(text) {
		return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
	},
	encodePointerComponent: function (component) {
		return component.toString().replace("~", "~0").replace("/", "~1");
	},
	decodePointerComponent: function (component) {
		return component.toString().replace("~1", "/").replace("~0", "~");
	},
	splitPointer: function (pointerString) {
		var parts = pointerString.split("/");
		if (parts[0] == "") {
			parts.shift();
		}
		for (var i = 0; i < parts.length; i++) {
			parts[i] = Utils.decodePointerComponent(parts[i]);
		}
		return parts;
	},
	joinPointer: function (pointerComponents) {
		var result = "";
		for (var i = 0; i < parts.length; i++) {
			result += "/" + Utils.encodePointerComponent(parts[i]);
		}
		return result;
	}
};
(function () {
	var counter = 0;
	Utils.getUniqueKey = function () {
		return counter++;
	};
})();

// Place relevant ones in the public API

publicApi.getMonitorKey = Utils.getUniqueKey;
publicApi.getKeyVariant = function (baseKey, variantName) {
	return Utils.getKeyVariant(baseKey, "~" + variantName);
};
publicApi.keyIsVariant = Utils.keyIsVariant;
publicApi.log = function (level, message) {
	if (typeof level != "number") {
		alert("First argument to log() must be a number (preferably enum value from .logLevel)");
		throw new Error("First argument to log() must be a number (preferably enum value from .logLevel)");
	} else {
		Utils.log(level, message);
	}
};
publicApi.setLogFunction = function (log) {
	Utils.log = log;
};
publicApi.logLevel = Utils.logLevel;
publicApi.encodeData = Utils.encodeData;
publicApi.decodeData = Utils.decodeData;
publicApi.encodePointerComponent = Utils.encodePointerComponent;
publicApi.decodePointerComponent = Utils.decodePointerComponent;
publicApi.splitPointer = Utils.splitPointer;
publicApi.joinPointer = Utils.joinPointer;
publicApi.escapeHtml = Utils.escapeHtml;

publicApi.extend = function (obj) {
	for (var key in obj) {
		if (publicApi[key] == undefined) {
			publicApi[key] = obj[key];
		}
	}
};

function cacheResult(targetObj, map) {
	for (var key in map) {
		(function (key, value) {
			targetObj[key] = function () {
				return value;
			};
		})(key, map[key]);
	}
}

function MonitorSet(context) {
	this.contents = {};
	this.keyOrder = [];
	this.context = context;
}
MonitorSet.prototype = {
	add: function (monitorKey, monitor) {
		if (typeof monitorKey != "string" && typeof monitorKey != "number") {
			throw new Error("First argument must be a monitorKey, obtained using getMonitorKey()");
		}
		this.contents[monitorKey] = monitor;
		this.addKey(monitorKey);
	},
	addKey: function (monitorKey) {
		var i;
		for (i = 0; i < this.keyOrder.length; i++) {
			var key = this.keyOrder[i];
			if (key == monitorKey) {
				return;
			}
			if (Utils.keyIsVariant(monitorKey, key)) {
				this.keyOrder.splice(i, 0, monitorKey);
				return;
			}
		}
		this.keyOrder.push(monitorKey);
	},
	remove: function (monitorKey) {
		delete this.contents[monitorKey];
		this.removeKey(monitorKey);
		var prefix = monitorKey + ".";
		for (var key in this.contents) {
			if (key.substring(0, prefix.length) == prefix) {
				this.removeKey(key);
				delete this.contents[key];
			}
		}
	},
	removeKey: function (monitorKey) {
		var index = this.keyOrder.indexOf(monitorKey);
		if (index >= 0) {
			this.keyOrder.splice(index, 1);
		}
	},
	notify: function () {
		var notifyArgs = arguments;
		for (var i = 0; i < this.keyOrder.length; i++) {
			var key = this.keyOrder[i];
			var monitor = this.contents[key];
			monitor.apply(this.context, notifyArgs);
		}
	},
	isEmpty: function () {
		var key;
		for (key in this.contents) {
			if (this.contents[key].length !== 0) {
				return false;
			}
		}
		return true;
	}
};

function ListenerSet(context) {
	this.listeners = [];
	this.context = context;
}
ListenerSet.prototype = {
	add: function (listener) {
		this.listeners[this.listeners.length] = listener;
	},
	notify: function () {
		var listenerArgs = arguments;
		while (this.listeners.length > 0) {
			var listener = this.listeners.shift();
			listener.apply(this.context, listenerArgs);
		}
	},
	isEmpty: function () {
		return this.listeners.length === 0;
	}
};

// DelayedCallbacks is used for notifications that might be external to the library
// The callbacks are still executed synchronously - however, they are not executed while the system is in a transitional state.
var DelayedCallbacks = {
	depth: 0,
	callbacks: [],
	increment: function () {
		this.depth++;
	},
	decrement: function () {
		this.depth--;
		if (this.depth < 0) {
			throw new Error("DelayedCallbacks.depth cannot be < 0");
		}
		while (this.depth == 0 && this.callbacks.length > 0) {
			var callback = this.callbacks.shift();
			this.depth++;
			callback();
			this.depth--
		}
	},
	add: function (callback) {
		this.depth++;
		this.callbacks.push(callback);
		this.decrement();
	}
};

if (typeof XMLHttpRequest == "undefined") {
	XMLHttpRequest = function () {
		try {
			return new ActiveXObject("Msxml2.XMLHTTP.6.0");
		} catch (e) {
		}
		try {
			return new ActiveXObject("Msxml2.XMLHTTP.3.0");
		} catch (e) {
		}
		try {
			return new ActiveXObject("Microsoft.XMLHTTP");
		} catch (e) {
		}
		//Microsoft.XMLHTTP points to Msxml2.XMLHTTP and is redundanat
		throw new Error("This browser does not support XMLHttpRequest.");
	};
}

// Default cache
(function () {
	var cacheData = {};
	var cacheTimes = {};
	var emptyTimeout = setInterval(function () {
		defaultCache.empty();
	}, 10*1000);

	var defaultCache = function (cacheKey, insertData) {
		if (insertData !== undefined) {
			cacheData[cacheKey] = insertData;
			cacheTimes[cacheKey] = (new Date()).getTime();
			return;
		}
		return cacheData[cacheKey];
	};
	defaultCache.cacheSeconds = 10;
	defaultCache.empty = function (timeLimit) {
		// TODO: figure out what to do here
		return;
		if (timeLimit == undefined) {
			timeLimit = (new Date()).getTime() - defaultCache.cacheSeconds * 1000;
		}
		for (var key in cacheTimes) {
			if (cacheTimes[key] <= timeLimit) {
				var request = cacheData[key];
				delete cacheData[key];
				delete cacheTimes[key];
			}
		}
	};
	defaultCache.invalidate = function (urlPattern) {
		if (typeof urlPattern == "string") {
			urlPattern = Utils.resolveRelativeUri(urlPattern);
		}
		for (var key in cacheData) {
			var request = cacheData[key];
			var url = request.url;
			if (typeof urlPattern == "string") {
				if (url.indexOf(urlPattern) != -1) {
					request.invalidate();
				}
			} else {
				if (urlPattern.test(url)) {
					request.invalidate();
				}
			}
		}
	};
	publicApi.defaultCache = defaultCache;
	publicApi.invalidate = defaultCache.invalidate;
})();

function FragmentRequest(request, fragment) {
	var thisFragmentRequest = this;
	
	this.baseUrl = request.url;
	this.fragment = fragment;
	if (fragment == null) {
		fragment = "";
	}
	this.url = this.baseUrl + "#" + encodeURI(fragment);

	this.getRoot = function (callback) {
		request.getRoot(function(data) {
			callback.call(data, data, thisFragmentRequest);
		});
	};
	this.getData = function (callback) {
		if (fragment == null || fragment == "") {
			request.document.getRoot(function(data) {
				callback.call(data, data, thisFragmentRequest);
			});
		} else {
			request.document.getFragment(fragment, function(data) {
				callback.call(data, data, thisFragmentRequest);
			});
		}
	};
	this.getRawResponse = function (callback) {
		request.getResponse(function(data) {
			callback.call(data, data, thisFragmentRequest);
		});
	};
}
FragmentRequest.prototype = {
}

function requestJson(url, method, data, encType, cacheFunction, hintSchema) {
	if (url == undefined) {
		throw new Error("URL cannot be undefined");
	}
	url = Utils.resolveRelativeUri(url);
	if (method == undefined) {
		method = "GET";
	}
	if (data === undefined) {
		data = {};
	}
	var fragment = null;
	var index = url.indexOf("#");
	if (index >= 0) {
		fragment = decodeURI(url.substring(index + 1));
		url = url.substring(0, index);
	}

	// TODO: think about implementing Rails-style _method=put/delete
	if (encType == undefined) {
		if (method == "GET") {
			encType = "application/x-www-form-urlencoded";
		} else if (method == "POST" || method == "PUT") {
			encType = "application/json";
		} else {
			encType = "application/x-www-form-urlencoded";
		}
	}
	if (cacheFunction == undefined) {
		cacheFunction = publicApi.defaultCache;
	}

	var cacheable = (cacheFunction && method == "GET" && encType == "application/x-www-form-urlencoded");
	if (cacheable) {
		var cacheKey = JSON.stringify(url) + ":" + JSON.stringify(data);
		var result = cacheFunction(cacheKey);
		if (result != undefined) {
			return new FragmentRequest(result, fragment);
		}
	}
	var request = new Request(url, method, data, encType, hintSchema);
	if (cacheable) {
		cacheFunction(cacheKey, request);
	}
	return new FragmentRequest(request, fragment);
}

function addToCache(url, rawData, schemaUrl, cacheFunction) {
	url = Utils.resolveRelativeUri(url);
	if (cacheFunction == undefined) {
		cacheFunction = publicApi.defaultCache;
	}
	var data = {};
	var cacheKey = JSON.stringify(url) + ":" + JSON.stringify(data);
	var request = new RequestFake(url, rawData, schemaUrl, cacheFunction, cacheKey);
}
publicApi.addToCache = addToCache;
publicApi.getData = function(params, callback, hintSchema) {
	if (typeof params == "string") {
		params = {url: params};
	}
	var request = requestJson(params.url, params.method, params.data, params.encType, null, hintSchema);
	if (callback != undefined) {
		request.getData(callback);
	}
	return request;
};
publicApi.isRequest = function (obj) {
	return (obj instanceof Request) || (obj instanceof FragmentRequest);
}

var PROFILE_SCHEMA_KEY = Utils.getUniqueKey();

function Request(url, method, data, encType, hintSchema) {
	url = Utils.resolveRelativeUri(url);

	data = Utils.encodeData(data, encType);
	if (method == "GET" && data != "") {
		if (url.indexOf("?") == -1) {
			url += "?";
		} else {
			url += "&";
		}
		url += data;
		data = "";
	}

	Utils.log(Utils.logLevel.STANDARD, "Sending request for: " + url);
	var thisRequest = this;
	this.successful = undefined;
	this.errorMessage = undefined;
	this.url = url;

	var isDefinitive = (data == undefined) || (data == "");
	this.responseListeners = new ListenerSet(this);
	this.document = new Document(url, isDefinitive, true);

	this.fetched = false;
	this.fetchData(url, method, data, encType, hintSchema);
	this.invalidate = function() {
		if (method == "GET") {
			this.fetchData(url, method, data, encType, hintSchema);
		}
	};
}
Request.prototype = {
	beingUsed: function() {
		if (this.baseContext == undefined) {
			Utils.log(Utils.logLevel.DEBUG, "No base context: " + this.url);
			return true;
		}
		return this.baseContext.retainCount() > 0;
	},
	getResponse: function (listener) {
		this.responseListeners.add(listener);
		this.checkForFullResponse();
	},
	checkForFullResponse: function () {
		if (this.document.raw.defined()) {
			this.responseListeners.notify(this.document.raw, this);
		}
	},
	ajaxSuccess: function (data, headerText, hintSchema) {
		this.fetched = true;
		var thisRequest = this;
		thisRequest.successful = true;
		Utils.log(Utils.logLevel.STANDARD, "Request success: " + this.url);
		var lines = headerText.replace(/\r\n/g, "\n").split("\n");
		var headers = {};
		var contentType = null;
		var contentTypeParameters = {};
		for (var i = 0; i < lines.length; i++) {
			var keyName = lines[i].split(": ")[0];
			if (keyName == "") {
				continue;
			}
			var value = lines[i].substring(keyName.length + 2);
			if (value[value.length - 1] == "\r") {
				value = value.substring(0, value.length - 1);
			}
			// Some browsers have all parameters as lower-case, so we do this for compatability
			//       (discovered using Dolphin Browser on an Android phone)
			keyName = keyName.toLowerCase();
			if (headers[keyName] == undefined) {
				headers[keyName] = value;
			} else if (typeof headers[keyName] == "object") {
				headers[keyName].push(value);
			} else {
				headers[keyName] = [headers[keyName], value];
			}
		}
		Utils.log(Utils.logLevel.DEBUG, "headers: " + JSON.stringify(headers, null, 4));
		var contentType = headers["content-type"].split(";")[0];
		var profileParts = headers["content-type"].substring(contentType.length + 1).split(",");
		for (var i = 0; i < profileParts.length; i++) {
			var partName = profileParts[i].split("=")[0];
			var partValue = profileParts[i].substring(partName.length + 1);
			partName = partName.trim();
			if (partName == "") {
				continue;
			}
			contentTypeParameters[partName] = partValue;
		}

		thisRequest.headers = headers;
		thisRequest.contentType = contentType;
		thisRequest.contentTypeParameters = contentTypeParameters;

		thisRequest.document.setRaw(data);
		thisRequest.profileUrl = null;
		thisRequest.document.raw.removeSchema(PROFILE_SCHEMA_KEY);
		if (contentTypeParameters["profile"] != undefined) {
			var schemaUrl = contentTypeParameters["profile"];
			schemaUrl = Utils.resolveRelativeUri(thisRequest.url, schemaUrl);
			thisRequest.profileUrl = schemaUrl;
			thisRequest.document.raw.addSchema(schemaUrl, PROFILE_SCHEMA_KEY);
		} else if (hintSchema != undefined) {
			thisRequest.document.raw.addSchema(hintSchema, PROFILE_SCHEMA_KEY);
		}
		if (contentTypeParameters["root"] != undefined) {
			var link = {
				"href": contentTypeParameters["root"],
				"rel": "root"
			};
			thisRequest.document.raw.addLink(link);
		}
		
		// Links
		if (headers["link"]) {
			var links = (typeof headers["link"] == "object") ? headers['link'] : [headers['link']];
			for (var i = 0; i < links.length; i++) {
				var link = links[i];
				var parts = link.trim().split(";");
				var url = parts.shift().trim();
				url = url.substring(1, url.length - 2);
				var linkObj = {
					"href": url
				};
				for (var j = 0; j < parts.length; j++) {
					var part = parts[j];
					var key = part.substring(0, part.indexOf("=")).trim();
					var value = part.substring(key.length + 1);
					if (value.charAt(0) == '"') {
						value = JSON.parse(value);
					}
					if (key == "type") {
						key = "mediaType";
					}
					linkObj[key] = value;
				}
				thisRequest.document.raw.addLink(linkObj);
			}
		}

		thisRequest.checkForFullResponse();
		thisRequest.document.raw.whenSchemasStable(function () {
			var rootLink = thisRequest.document.raw.getLink("root");
			if (rootLink != undefined) {
				var fragment = decodeURI(rootLink.href.substring(rootLink.href.indexOf("#") + 1));
				thisRequest.document.setRoot(fragment);
			} else {
				thisRequest.document.setRoot("");
			}
		});
	},
	ajaxError: function (message) {
		this.fetched = true;
		var thisRequest = this;
		thisRequest.successful = false;
		thisRequest.errorMessage = message;
		Utils.log(Utils.logLevel.WARNING, "Error fetching: " + this.url + " (" + message + ")");
		thisRequest.document.setRaw(undefined);
		thisRequest.document.raw.whenSchemasStable(function () {
			thisRequest.checkForFullResponse();
			thisRequest.document.setRoot("");
		});
	},
	fetchData: function(url, method, data, encType, hintSchema) {
		var thisRequest = this;
		var xhr = new XMLHttpRequest();
		xhr.onreadystatechange = function () {
			if (xhr.readyState == 4) {
				if (xhr.status == 200) {
					var data = xhr.responseText;
					try {
						data = JSON.parse(data);
					} catch (e) {
						thisRequest.ajaxError(e);
						return;
					}
					var headers = xhr.getAllResponseHeaders();
					if (headers == "") {	// Firefox bug  >_>
						headers = [];
						var desiredHeaders = ["Cache-Control", "Content-Language", "Content-Type", "Expires", "Last-Modified", "Pragma"];
						for (var i = 0; i < desiredHeaders.length; i++) {
							var value = xhr.getResponseHeader(desiredHeaders[i]);
							if (value != "" && value != null) {
								headers.push(desiredHeaders[i] + ": " + value);
							}
						}
						headers = headers.join("\n");
					}
					thisRequest.ajaxSuccess(data, headers, hintSchema);
				} else {
					thisRequest.ajaxError("HTTP Status " + xhr.status);
				}
			}
		};
		var xhrUrl = url;
		var xhrData = data;
		if ((method == "GET" || method == "DELETE") && (xhrData != undefined && xhrData != "")) {
			if (xhrUrl.indexOf("?") == -1) {
				xhrUrl += "?";
			} else {
				xhrUrl += "&";
			}
			xhrUrl += xhrData;
			xhrData = undefined;
		}
		if (publicApi.config.antiCacheUrls) {
			var extra = "_=" + Math.random();
			if (xhrUrl.indexOf("?") == -1) {
				xhrUrl += "?" + extra;
			} else {
				xhrUrl += "&" + extra;
			}
		}
		xhr.open(method, xhrUrl, true);
		xhr.setRequestHeader("Content-Type", encType);
		xhr.setRequestHeader("If-Modified-Since", "Thu, 01 Jan 1970 00:00:00 GMT");
		xhr.send(xhrData);
	}
};

function RequestFake(url, rawData, schemaUrl, cacheFunction, cacheKey) {
	cacheFunction(cacheKey, this);

	var thisRequest = this;
	this.url = url;
	
	this.responseListeners = new ListenerSet(this);
	this.document = new Document(url, true, true);
	this.document.setRaw(rawData);
	this.profileUrl = schemaUrl;
	if (schemaUrl != undefined) {
		this.document.raw.addSchema(schemaUrl);
	}
	if (url == schemaUrl) {
		this.document.setRoot("");
	} else {
		this.document.raw.whenSchemasStable(function () {
			var rootLink = thisRequest.document.raw.getLink("root");
			if (rootLink != undefined) {
				var fragment = decodeURI(rootLink.href.substring(rootLink.href.indexOf("#") + 1));
				thisRequest.document.setRoot(fragment);
			} else {
				thisRequest.document.setRoot("");
			}
		});
	}
	this.successful = true;
	this.errorMessage = undefined;

	this.fetched = false;
	this.invalidate = function() {
		this.fetchData(url, "GET", undefined, "application/x-www-form-urlencoded", schemaUrl);
	};
}
RequestFake.prototype = Request.prototype;


function Patch(prefix) {
	this.operations = [];
	if (prefix == undefined) {
		prefix = "";
	}
	this.prefix = prefix;
}
Patch.prototype = {
	isEmpty: function () {
		return this.operations.length == 0;
	},
	each: function (callback) {
		for (var i = 0; i < this.operations.length; i++) {
			callback.call(this, i, this.operations[i]);
		}
		return this;
	},
	plain: function () {
		var result = [];
		for (var i = 0; i < this.operations.length; i++) {
			result[i] = this.operations[i].plain();
		}
		return result;
	},
	condense: function () {
		// Replace operations with shorter sequence, if possible
		return;
	},
	filterImmediate: function () {
		var subPatch = new Patch(this.prefix);
		for (var i = 0; i < this.operations.length; i++) {
			var operation = this.operations[i];
			if (operation.immediateChild(this.prefix)) {
				subPatch.operations.push(operation);
			}
		}
		return subPatch;
	},
	filter: function (prefix) {
		prefix = this.prefix + prefix;
		var subPatch = new Patch(prefix);
		for (var i = 0; i < this.operations.length; i++) {
			var operation = this.operations[i];
			if (operation.hasPrefix(prefix)) {
				subPatch.operations.push(operation);
			}
		}
		return subPatch;
	},
	filterRemainder: function (prefix) {
		prefix = this.prefix + prefix;
		var subPatch = new Patch(this.prefix);
		for (var i = 0; i < this.operations.length; i++) {
			var operation = this.operations[i];
			if (!operation.hasPrefix(prefix)) {
				subPatch.operations.push(operation);
			}
		}
		return subPatch;
	},
	replace: function (path, value) {
		var operation = new PatchOperation("replace", path, value);
		this.operations.push(operation);
		return this;
	},
	add: function (path, value) {
		var operation = new PatchOperation("add", path, value);
		this.operations.push(operation);
		return this;
	},
	remove: function (path) {
		var operation = new PatchOperation("remove", path);
		this.operations.push(operation);
		return this;
	},
	move: function (path, target) {
		var operation = new PatchOperation("move", path, target);
		this.operations.push(operation);
		return this;
	},
	inverse: function () {
		var result = new Patch(this.prefix);
		for (var i = 0; i < this.operations.length; i++) {
			result.operations[i] = this.operations[i].inverse();
		}
		result.operations.reverse();
		return result;
	}
};

function PatchOperation(patchType, subject, value) {
	this._patchType = patchType;
	this._subject = subject;
	this._subjectValue = undefined;
	if (patchType == "move") {
		this._target = value;
	} else {
		this._value = value;
	}
}
PatchOperation.prototype = {
	action: function () {
		return this._patchType;
	},
	value: function () {
		return this._value;
	},
	subject: function () {
		return this._subject;	
	},
	setSubjectValue: function (value) {
		this._subjectValue = value;
		return this;
	},
	subjectValue: function () {
		return this._subjectValue;
	},
	inverse: function () {
		switch (this._patchType) {
			case "replace":
				return new PatchOperation("replace", this._subject, this._subjectValue);
			case "add":
				return (new PatchOperation("remove", this._subject)).setSubjectValue(this._value);
			case "remove":
				return (new PatchOperation("add", this._subject, this._subjectValue));
			case "move":
				return (new PatchOperation("move", this._target, this._subject));
			default:
				throw new Error("Unrecognised patch type for inverse: " + this._patchType);
		}
	},
	depthFrom: function (path) {
		if (typeof path == "object") {
			path = path.pointerPath();
		}
		path += "/";
		var minDepth = NaN;
		if (this._subject.substring(0, path.length) == path) {
			var remainder = this._subject.substring(path.length);
			if (remainder == 0) {
				minDepth = 0;
			} else {
				minDepth = remainder.split("/").length;
			}
		}
		if (this._target != undefined) {
			if (this._target.substring(0, path.length) == path) {
				var targetDepth;
				var remainder = this._target.substring(path.length);
				if (remainder == 0) {
					targetDepth = 0;
				} else {
					targetDepth = remainder.split("/").length;
				}
				if (!(targetDepth > minDepth)) {
					minDepth = targetDepth;
				}
			}
		}
		return minDepth;
	},
	subjectEquals: function (path) {
		return this._subject == path;
	},
	subjectChild: function (path) {
		path += "/";
		if (this._subject.substring(0, path.length) == path) {
			var remainder = this._subject.substring(path.length);
			if (remainder.indexOf("/") == -1) {
				return decodeURIComponent(remainder);
			}
		}
		return false;
	},
	subjectRelative: function (path) {
		path += "/";
		if (this._subject.substring(0, path.length) == path) {
			return this._subject.substring(path.length - 1);
		}
		return false;
	},
	target: function () {
		return this._target;
	},
	targetEquals: function (path) {
		return this._target == path;
	},
	targetChild: function (path) {
		if (this._target == undefined) {
			return;
		}
		path += "/";
		if (this._target.substring(0, path.length) == path) {
			var remainder = this._target.substring(path.length);
			if (remainder.indexOf("/") == -1) {
				return decodeURIComponent(remainder);
			}
		}
		return false;
	},
	targetRelative: function (path) {
		path += "/";
		if (this._target.substring(0, path.length) == path) {
			return this._target.substring(path.length - 1);
		}
		return false;
	},
	plain: function () {
		var result = {};
		result[this._patchType] = this._subject;
		if (this._patchType == "remove") {
		} else if (this._patchType == "move") {
			result.to = this._target;
		} else {
			result.value = this._value;
		}
		return result;
	},
	matches: function (prefix) {
		if (this._subject == prefix) {
			return true;
		} else if (this._patchType == "move" && this._target == prefix) {
			return true;
		}
		return false;
	},
	hasPrefix: function (prefix) {
		if (typeof prefix == "object") {
			prefix = prefix.pointerPath();
		}
		if (this.matches(prefix)) {
			return true;
		}
		prefix += "/";
		if (this._subject.substring(0, prefix.length) == prefix) {
			return true;
		} else if (this._patchType == "move" && this._target.substring(0, prefix.length) == prefix) {
			return true;
		}
		return false;
	}
};



var changeListeners = [];
publicApi.registerChangeListener = function (listener) {
	changeListeners.push(listener);
};

var batchChanges = false;
var batchChangeDocuments = [];
publicApi.batch = function (batchFunc) {
	if (batchFunc != undefined) {
		publicApi.batch();
		batchFunc();
		publicApi.batchDone();
		return this;
	}
	batchChanges = true;
	return this;
};
publicApi.batchDone = function () {
	batchChanges = false;
	while (batchChangeDocuments.length > 0) {
		var document = batchChangeDocuments.shift();
		var patch = document.batchPatch;
		delete document.batchPatch;
		document.patch(patch);
	}
	return this;
};

function Document(url, isDefinitive, readOnly) {
	var thisDocument = this;
	this.readOnly = !!readOnly;
	this.url = url;
	this.isDefinitive = isDefinitive;

	var rootPath = null;
	var rawSecrets = {};
	this.raw = new Data(this, rawSecrets);
	this.root = null;
	
	var documentChangeListeners = [];
	this.registerChangeListener = function (listener) {
		documentChangeListeners.push(listener);
	};
	
	function notifyChangeListeners(patch) {
		DelayedCallbacks.increment();
		var listeners = changeListeners.concat(documentChangeListeners);
		DelayedCallbacks.add(function () {
			for (var i = 0; i < listeners.length; i++) {
				listeners[i].call(thisDocument, patch, thisDocument);
			}
		});
		DelayedCallbacks.decrement();
	}

	this.setRaw = function (value) {
		var needsFakePatch = this.raw.defined();
		rawSecrets.setValue(value);
		// It's an update to a read-only document
		if (needsFakePatch) {
			rawSecrets.setValue(value);
			var patch = new Patch();
			patch.replace(this.raw.pointerPath(), value);
			notifyChangeListeners(patch);
		}
	};
	var rootListeners = new ListenerSet(this);
	this.getRoot = function (callback) {
		if (this.root == null) {
			rootListeners.add(callback);
		} else {
			callback.call(this, this.root);
		}
	};
	this.setRoot = function (newRootPath) {
		rootPath = newRootPath;
		this.root = this.raw.subPath(newRootPath);
		rootListeners.notify(this.root);
	};
	this.patch = function (patch) {
		if (this.readOnly) {
			throw new Error("Cannot update read-only document");
		}
		if (batchChanges) {
			if (this.batchPatch == undefined) {
				this.batchPatch = new Patch();
				batchChangeDocuments.push(this);
			}
			this.batchPatch.operations = this.batchPatch.operations.concat(patch.operations);
			return;
		}
		DelayedCallbacks.increment();
		var rawPatch = patch.filter("?");
		var rootPatch = patch.filterRemainder("?");
		this.raw.patch(rawPatch);
		this.root.patch(rootPatch);
		notifyChangeListeners(patch);
		DelayedCallbacks.decrement();
	};
	this.affectedData = function (operation) {
		var subject = operation.subject();
		var subjectData = null;
		if (subject == "?" || subject.substring(0, 2) == "?/") {
			subjectData = this.raw.subPath(subject.substring(1));
		} else {
			subjectData = this.root.subPath(subject);
		}
		var result = [];
		while (subjectData != undefined) {
			result.push(subjectData);
			subjectData = subjectData.parent();
		}
		if (operation.action() == "move") {
			var target = operation.target();
			var targetData = null;
			if (target == "?" || target.substring(0, 2) == "?/") {
				targetData = this.raw.subPath(target.substring(1));
			} else {
				targetData = this.root.subPath(target);
			}
			result.push();
			while (targetData != undefined) {
				result.push(targetData);
				targetData = targetData.parent();
			}
		}
		return result;
	}
}

Document.prototype = {
	resolveUrl: function (url) {
		return Uri.resolve(this.url, url);
	},
	getFragment: function (fragment, callback) {
		this.getRoot(function (data) {
			if (fragment == "") {
				callback.call(this, data);
			} else {
				var fragmentData = data.subPath(fragment);
				callback.call(this, fragmentData);
			}
		});
	},
	get: function (path) {
		return this.root.get(path);
	},
	set: function (path, value) {
		this.root.set(path, value);
		return this;
	},
	move: function (source, target) {
		var patch = new Patch();
		patch.move(source, target);
		this.patch(patch);
		return this;
	}
}

var INDEX_REGEX = /^(0|[1-9]\d*)$/
function isIndex(value) {
	return INDEX_REGEX.test(value);
}

var uniqueIdCounter = 0;
function Data(document, secrets, parent, parentKey) {
	this.uniqueId = uniqueIdCounter++;
	this.document = document;
	this.readOnly = function () {
		return document.readOnly;
	};
	
	var value = undefined;
	var basicType = undefined;
	var length = 0;
	var keys = [];
	var propertyData = {};
	var propertyDataSecrets = {};
	this.property = function (key) {
		if (propertyData[key] == undefined) {
			propertyDataSecrets[key] = {};
			propertyData[key] = new Data(this.document, propertyDataSecrets[key], this, key);
			if (basicType == "object") {
				propertyDataSecrets[key].setValue(value[key]);
				if (value[key] !== undefined) {
					secrets.schemas.addSchemasForProperty(key, propertyData[key]);
				}
			}
		}
		return propertyData[key];
	};
	var indexData = {};
	var indexDataSecrets = {};
	this.item = function (index) {
		if (!isIndex(index)) {
			throw new Error("Index must be a positive integer (or integer-value string)");
		}
		if (indexData[index] == undefined) {
			indexDataSecrets[index] = {};
			indexData[index] = new Data(this.document, indexDataSecrets[index], this, index);
			if (basicType == "array") {
				indexDataSecrets[index].setValue(value[index]);
				if (value[index] !== undefined) {
					secrets.schemas.addSchemasForIndex(index, indexData[index]);
				}
			}
		}
		return indexData[index];
	}
	
	this.parent = function() {
		return parent;
	};
	this.parentKey = function () {
		return parentKey;
	};
	this.pointerPath = function () {
		if (this.document.root == this) {
			return "";
		} else if (parent != undefined) {
			return parent.pointerPath() + "/" + Utils.encodePointerComponent(parentKey);
		} else {
			return "?";
		}
	};
	
	this.basicType = function() {
		return basicType;
	};
	this.value = function() {
		if (basicType == "object") {
			var result = {};
			for (var i = 0; i < keys.length; i++) {
				var key = keys[i];
				if (propertyData[key] != undefined) {
					result[key] = propertyData[key].value();
				} else {
					result[key] = value[key];
				}
			}
			return result;
		} else if (basicType == "array") {
			var result = [];
			for (var i = 0; i < length; i++) {
				if (indexData[i] != undefined) {
					result[i] = indexData[i].value();
				} else {
					result[i] = value[i];
				}
			}
			return result;
		} else {
			return value;
		}
	};
	this.keys = function () {
		return keys.slice(0);
	};
	this.length = function () {
		return length;
	};
	
	this.patch = function (patch) {
		var thisData = this;
		var thisPath = this.pointerPath();
		var updateKeys = {};
		patch.each(function (i, operation) {
			if (operation.subjectEquals(thisPath)) {
				if (operation.action() == "replace" || operation.action() == "add") {
					operation.setSubjectValue(thisData.value());
					secrets.setValue(operation.value());
					if (basicType == "object") {
						
					}
				} else if (operation.action() == "remove") {
				} else if (operation.action() == "move") {
				} else {
					throw new Error("Unrecognised patch operation: " + operation.action());
				}
			} else if (operation.targetEquals(thisPath)) {
				if (operation.action() == "move") {
					secrets.setValue(operation.subjectValue());
				}
			} else {
				var child = operation.subjectChild(thisPath);
				if (child) {
					updateKeys[child] = true;
					if (basicType == "object") {
						if (operation.action() == "add") {
							var keyIndex = keys.indexOf(child);
							if (keyIndex != -1) {
								throw new Error("Cannot add existing key: " + child);
							}
							keys.push(child);
							value[child] = operation.value();
							if (propertyData[child] != undefined) {
								propertyDataSecrets[child].setValue(operation.value());
								secrets.schemas.addSchemasForProperty(child, propertyData[child]);
							}
						} else if (operation.action() == "remove" || operation.action() == "move") {
							var keyIndex = keys.indexOf(child);
							if (keyIndex == -1) {
								throw new Error("Cannot delete missing key: " + child);
							}
							operation.setSubjectValue(thisData.propertyValue(child));
							keys.splice(keyIndex, 1);
							if (propertyDataSecrets[child] != undefined) {
								propertyDataSecrets[child].setValue(undefined);
							}
							delete value[child];
						} else if (operation.action() == "replace") {
						} else {
							throw new Error("Unrecognised patch operation: " + operation.action());
						}
					} else if (basicType == "array") {
						if (!isIndex(child)) {
							throw new Error("Cannot patch non-numeric index: " + child);
						}
						var index = parseInt(child);
						if (operation.action() == "add") {
							if (index > length) {
								throw new Error("Cannot add past the end of the list");
							}
							for (var j = length - 1; j >= index; j--) {
								if (indexDataSecrets[j + 1] == undefined) {
									continue;
								}
								if (indexData[j] == undefined) {
									indexDataSecrets[j + 1].setValue(value[j]);
								} else {
									indexDataSecrets[j + 1].setValue(indexData[j].value());
								}
							}
							value.splice(index, 0, operation.value());
							length++;
							if (indexData[value.length - 1] != undefined) {
								secrets.schemas.addSchemasForIndex(value.length - 1, indexData[value.length - 1]);
							}
						} else if (operation.action() == "remove" || operation.action() == "move") {
							if (index >= length) {
								throw new Error("Cannot remove a non-existent index");
							}
							operation.setSubjectValue(thisData.itemValue(index));
							for (var j = index; j < length - 1; j++) {
								if (indexDataSecrets[j] == undefined) {
									continue;
								}
								if (indexData[j + 1] == undefined) {
									indexDataSecrets[j].setValue(value[j + 1]);
								} else {
									indexDataSecrets[j].setValue(indexData[j + 1].value());
								}
							}
							if (indexDataSecrets[length - 1] != undefined) {
								indexDataSecrets[length - 1].setValue(undefined);
							}
							length--;
							value.splice(index, 1);
						} else if (operation.action() == "replace") {
						} else {
							throw new Error("Unrecognised patch operation: " + operation.action());
						}
					}
				}
				var targetChild = operation.targetChild(thisPath);
				if (targetChild) {
					updateKeys[targetChild] = true;
					if (basicType == "object") {
						if (operation.action() == "move") {
							var keyIndex = keys.indexOf(targetChild);
							if (keyIndex != -1) {
								throw new Error("Cannot move to existing key: " + targetChild);
							}
							keys.push(targetChild);
							value[targetChild] = operation.subjectValue();
							if (propertyData[targetChild] != undefined) {
								secrets.schemas.addSchemasForProperty(targetChild, propertyData[targetChild]);
							}
						}
					} else if (basicType == "array") {
						if (!isIndex(targetChild)) {
							throw new Error("Cannot patch non-numeric index: " + targetChild);
						}
						var index = parseInt(targetChild);
						if (operation.action() == "move") {
							if (index > length) {
								throw new Error("Cannot add past the end of the list");
							}
							for (var j = length - 1; j >= index; j--) {
								if (indexDataSecrets[j + 1] == undefined) {
									continue;
								}
								if (indexData[j] == undefined) {
									indexDataSecrets[j + 1].setValue(value[j]);
								} else {
									indexDataSecrets[j + 1].setValue(indexData[j].value());
								}
							}
							value.splice(index, 0, operation.subjectValue());
							length++;
							if (indexData[value.length - 1] != undefined) {
								secrets.schemas.addSchemasForIndex(value.length - 1, indexData[value.length - 1]);
							}
						}
					}
				}
			}
		});
		if (basicType == "object") {
			for (var i = 0; i < keys.length; i++) {
				var key = keys[i];
				var subPatch = patch.filter("/" + Utils.encodePointerComponent(key));
				if (!subPatch.isEmpty()) {
					this.property(key).patch(subPatch);
				}
			}
		} else if (basicType == "array") {
			for (var i = 0; i < length; i++) {
				var subPatch = patch.filter("/" + Utils.encodePointerComponent(i));
				if (!subPatch.isEmpty()) {
					this.index(i).patch(subPatch);
				}
			}
		} else {
			// TODO: throw a wobbly
		}
		for (var key in updateKeys) {
			secrets.schemas.update(key);
		}
	};
	
	secrets.setValue = function (newValue) {
		var newBasicType = Utils.guessBasicType(newValue, basicType);
		var oldValue = value;
		value = newValue;
		if (newBasicType != basicType) {
			if (basicType == "object") {
				for (var key in propertyData) {
					propertyDataSecrets[key].setValue(undefined);
				}
			} else if (basicType == "array") {
				for (var index in indexData) {
					indexDataSecrets[index].setValue(undefined);
				}
			}
			basicType = newBasicType;
		}
		if (newBasicType == "object") {
			for (var key in propertyData) {
				if (newValue.hasOwnProperty(key)) {
					if (!propertyData[key].defined()) {
						secrets.schemas.addSchemasForProperty(key, propertyData[key]);
					}
					propertyDataSecrets[key].setValue(newValue[key]);
				} else {
					propertyDataSecrets[key].setValue(undefined);
				}
			}
			keys = Object.keys(newValue);
			length = 0;
		} else if (newBasicType == "array") {
			for (var index in indexData) {
				if (index < newValue.length) {
					if (!indexData[index].defined()) {
						secrets.schemas.addSchemasForIndex(index, indexData[index]);
					}
					indexDataSecrets[index].setValue(newValue[index]);
				} else {
					indexDataSecrets[index].setValue(undefined);
				}
			}
			keys = [];
			length = newValue.length;
		} else {
			keys = [];
			length = 0;
		}
		if (newValue === undefined) {
			if (oldValue !== undefined) {
				// we check oldValue, so we don't get a "schema changed" callback when we access an undefined property/index.
				secrets.schemas.clear();
			}
		} else {
			secrets.schemas.update(null);
		}
	};
	
	secrets.schemas = new SchemaSet(this);
	this.schemas = function () {
		return secrets.schemas.getSchemas();
	};
	this.whenSchemasStable = function(callback) {
		secrets.schemas.whenSchemasStable(callback);
		return this;
	};
	this.links = function (rel) {
		return secrets.schemas.getLinks(rel);
	};
	this.addLink = function (rawLink) {
		secrets.schemas.addLink(rawLink);
		return this;
	};
	this.addSchema = function (schema, schemaKey) {
		var thisData = this;
		if (schema instanceof SchemaList) {
			schema.each(function (index, schema) {
				thisData.addSchema(schema, schemaKey);
			});
		} else {
			secrets.schemas.addSchema(schema, schemaKey);
		}
		return this;
	};
	this.removeSchema = function ( schemaKey) {
		secrets.schemas.removeSchema(schemaKey);
		return this;
	};
	this.addSchemaMatchMonitor = function (monitorKey, schema, monitor, executeImmediately, impatientCallbacks) {
		return secrets.schemas.addSchemaMatchMonitor(monitorKey, schema, monitor, executeImmediately, impatientCallbacks);
	};
}
Data.prototype = {
	referenceUrl: function () {
		if (this.document.isDefinitive) {
			var pointerPath = this.pointerPath();
			if (pointerPath == "" || pointerPath.charAt(0) == "/") {
				return this.document.url + "#" + encodeURI(this.pointerPath());
			}
		}
	},
	subPath: function (path) {
		var parts = path.split("/");
		if (parts[0] != "") {
			throw new Error("Path must begin with / (or be empty)");
		}
		var result = this;
		for (var i = 1; i < parts.length; i++) {
			parts[i] = Utils.decodePointerComponent(parts[i]);
			if (result.basicType() == "array") {
				result = result.index(parts[i]);
			} else {
				result = result.property(parts[i]);
			}
		}
		return result;
	},
	defined: function () {
		return this.basicType() != undefined;
	},
	setValue: function (newValue) {
		if (typeof newValue == "undefined") {
			return this.remove();
		}
		if (this.basicType() != "object" && this.basicType() != "array" && this.value() === newValue) {
			return this;
		}
		var patch = new Patch();
		if (this.defined()) {
			patch.replace(this.pointerPath(), newValue);
		} else {
			patch.add(this.pointerPath(), newValue);
		}
		this.document.patch(patch, this);
		return this;
	},
	remove: function () {
		var patch = new Patch();
		patch.remove(this.pointerPath());
		this.document.patch(patch, this);
		return this;
	},
	itemValue: function (index) {
		return this.index(index).value();
	},
	removeItem: function (index) {
		this.index(index).remove();
		return this;
	},
	insertItem: function (index, value) {
		if (this.basicType() != "array") {
			throw Error("cannot insert into a non-array");
		}
		var patch = new Patch();
		patch.add(this.item(index).pointerPath(), value);
		this.document.patch(patch, this);
		return this;
	},
	push: function (value) {
		if (this.basicType() == "array") {
			this.index(this.length()).setValue(value);
		} else {
			throw new Error("Can only push() on an array");
		}
		return this;
	},
	propertyValue: function (key) {
		return this.property(key).value();
	},
	removeProperty: function (key) {
		this.property(key).remove();
		return this;
	},
	moveTo: function (target) {
		if (typeof target == "object") {
			if (target.document != this.document) {
				var value = this.value();
				this.remove();
				target.setValue(value);
				return target;
			}
			target = target.pointerPath();
		}
		var patch = new Patch();
		var pointerPath = this.pointerPath();
		if (target == pointerPath) {
			return;
		}
		patch.move(pointerPath, target);
		this.document.patch(patch, this);
		return this.document.root.subPath(target);
	},
	getLink: function (rel) {
		var links = this.links(rel);
		return links[0];
	},
	equals: function (otherData) {
		var i;
		var basicType = this.basicType();
		if (basicType != otherData.basicType()) {
			return false;
		}
		if (basicType == "array") {
			if (this.length() !== otherData.length()) {
				return false;
			}
			for (i = 0; i < this.length(); i++) {
				if (!this.index(i).equals(otherData.index(i))) {
					return false;
				}
			}
			return true;
		} else if (basicType == "object") {
			var i;
			var keys = this.keys();
			var otherKeys = otherData.keys();
			if (keys.length != otherKeys.length) {
				return false;
			}
			keys.sort();
			otherKeys.sort();
			for (i = 0; i < keys.length; i++) {
				if (keys[i] !== otherKeys[i]) {
					return false;
				}
			}
			for (i = 0; i < keys.length; i++) {
				var key = keys[i];
				if (!this.property(key).equals(otherData.property(key))) {
					return false;
				}
			}
			return true;
		} else {
			return this.value() === otherData.value();
		}
	},
	readOnlyCopy: function () {
		if (this.readOnly()) {
			return this;
		}
		var copy = publicApi.create(this.value(), this.document.url + "#:copy", true);
		this.schemas().each(function (index, schema) {
			copy.addSchema(schema);
		});
		return copy;
	},
	editableCopy: function () {
		var copy = publicApi.create(this.value(), this.document.url + "#:copy", false);
		var schemaKey = Utils.getUniqueKey();
		this.schemas().fixed().each(function (index, schema) {
			copy.addSchema(schema, schemaKey);
		});
		return copy;
	},
	asSchema: function () {
		var schema = new Schema(this.readOnlyCopy());
		if (this.readOnly()) {
			cacheResult(this, {asSchema: schema});
		}
		return schema;
	},
	asLink: function (targetData) {
		var readOnlyCopy = this.readOnlyCopy();
		var linkDefinition = new PotentialLink(readOnlyCopy);
		var result;
		if (targetData == undefined) {
			result = linkDefinition.linkForData(this);
		} else {
			result = linkDefinition.linkForData(targetData);
		}
		if (this.readOnly()) {
			cacheResult(this, {asLink: result});
		}
		return result;
	},
	items: function (callback) {
		for (var i = 0; i < this.length(); i++) {
			var subData = this.index(i);
			callback.call(subData, i, subData);
		}
		return this;
	},
	properties: function (keys, callback, additionalCallback) {
		var dataKeys;
		if (typeof keys == 'function') {
			callback = keys;
			keys = this.keys();
		}
		if (callback) {
			for (var i = 0; i < keys.length; i++) {
				var subData = this.property(keys[i]);
				callback.call(subData, keys[i], subData);
			}
		}
		if (additionalCallback) {
			var dataKeys = this.keys();
			for (var i = 0; i < dataKeys.length; i++) {
				if (keys.indexOf(dataKeys[i]) == -1) {
					var subData = this.property(dataKeys[i]);
					additionalCallback.call(subData, dataKeys[i], subData);
				}
			}
		}
		return this;
	},
	resolveUrl: function (url) {
		var data = this;
		while (data) {
			var selfLink = data.getLink("self");
			if (selfLink) {
				return Uri.resolve(selfLink.href, url);
			}
			data = data.parent();
		}
		return this.document.resolveUrl(url);
	},
	get: function (path) {
		return this.subPath(path).value();
	},
	set: function (path, value) {
		this.subPath(path).setValue(value);
		return this;
	},
	json: function () {
		return JSON.stringify(this.value());
	}
};
Data.prototype.indices = Data.prototype.items;
Data.prototype.indexValue = Data.prototype.itemValue;
Data.prototype.removeIndex = Data.prototype.removeItem;
Data.prototype.index = function (index) {
	return this.item(index);
};

publicApi.extendData = function (obj) {
	for (var key in obj) {
		if (Data.prototype[key] == undefined) {
			Data.prototype[key] = obj[key];
		}
	}
};


publicApi.create = function (rawData, baseUrl, readOnly) {
	var rawData = (typeof rawData == "object") ? JSON.parse(JSON.stringify(rawData)) : rawData; // Hacky recursive copy
	var definitive = baseUrl != undefined;
	if (baseUrl != undefined && baseUrl.indexOf("#") != -1) {
		var remainder = baseUrl.substring(baseUrl.indexOf("#") + 1);
		if (remainder != "") {
			definitive = false;
		}
		baseUrl = baseUrl.substring(0, baseUrl.indexOf("#"));
	}
	var document = new Document(baseUrl, definitive, readOnly);
	document.setRaw(rawData);
	document.setRoot("");
	return document.root;
};
publicApi.isData = function (obj) {
	return obj instanceof Data;
};

Data.prototype.deflate = function () {
	var schemas = [];
	this.schemas().each(function (index, schema) {
		if (schema.referenceUrl() != undefined) {
			schemas.push(schema.referenceUrl());
		} else {
			schemas.push(schema.data.deflate());
		}
	});
	var result = {
		baseUrl: this.document.url,
		readOnly: this.readOnly(),
		value: this.value(),
		schemas: schemas
	}
	return result;
}
publicApi.inflate = function (deflated) {
	var data = publicApi.create(deflated.value, deflated.baseUrl, deflated.readOnly);
	for (var i = 0; i < deflated.schemas.length; i++) {
		var schema = deflated.schemas[i];
		if (typeof schema == "object") {
			var schema = publicApi.inflate(schema).asSchema();
		}
		data.addSchema(schema);
	}
	return data;
}

function getSchema(url, callback) {
	return publicApi.getData(url, function(data, fragmentRequest) {
		var schema = data.asSchema();
		if (callback != undefined) {
			callback.call(schema, schema, fragmentRequest);
		}
	});
}
publicApi.createSchema = function (rawData, baseUrl) {
	var data = publicApi.create(rawData, baseUrl, true);
	return data.asSchema();
};
publicApi.isSchema = function (obj) {
	return obj instanceof Schema;
};

publicApi.getSchema = getSchema;

var ALL_TYPES = ["null", "boolean", "integer", "number", "string", "array", "object"];
var TYPE_SCHEMAS = {};
function getTypeSchema(basicType) {
	if (TYPE_SCHEMAS[basicType] == undefined) {
		TYPE_SCHEMAS[basicType] = publicApi.createSchema({"type": basicType});
	}
	return TYPE_SCHEMAS[basicType];
}

function Schema(data) {
	this.data = data;
	var referenceUrl = data.referenceUrl();
	var id = data.propertyValue("id");
	// TODO: if id is set, then cache it somehow, so we can find it again?

	var potentialLinks = [];
	var i, linkData;
	var linkDefinitions = data.property("links");
	if (linkDefinitions !== undefined) {
		linkDefinitions.indices(function (index, subData) {
			potentialLinks[potentialLinks.length] = new PotentialLink(subData);
		});
	}
	this.links = function () {
		return potentialLinks.slice(0);
	};
	this.schemaTitle = this.title();	
}
Schema.prototype = {
	"toString": function () {
		return "<Schema " + this.data + ">";
	},
	referenceUrl: function () {
		return this.data.referenceUrl();
	},
	isFull: function () {
		var refUrl = this.data.propertyValue("$ref");
		return refUrl === undefined;
	},
	getFull: function (callback) {
		var refUrl = this.data.propertyValue("$ref");
		if (refUrl === undefined) {
			if (callback) {
				callback.call(this, this, undefined);
			}
			return this;
		}
		refUrl = this.data.resolveUrl(refUrl);
		if (refUrl.charAt(0) == "#" && (refUrl.length == 1 || refUrl.charAt(1) == "/")) {
			var documentRoot = this.data.document.root;
			var pointerPath = decodeURIComponent(refUrl.substring(1));
			var schema = documentRoot.subPath(pointerPath).asSchema();
			if (callback) {
				callback.call(schema, schema, null);
			} else {
				return schema;
			}
		} else if (callback) {
			getSchema(refUrl, callback);
		}
		return this;
	},
	title: function () {
		var title = this.data.propertyValue("title");
		if (title == undefined) {
			title = null;
		}
		return title;
	},
	hasDefault: function() {
		return this.data.property("default").defined();
	},
	defaultValue: function() {
		return this.data.propertyValue("default");
	},
	propertySchemas: function (key) {
		var schemas = [];
		var subSchema = this.data.property("properties").property(key);
		if (subSchema.defined()) {
			schemas.push(subSchema.asSchema());
		}
		this.data.property("patternProperties").properties(function (patternKey, subData) {
			var regEx = new RegExp(patternKey);
			if (regEx.test(key)) {
				schemas.push(subData.asSchema());
			}
		});
		if (schemas.length == 0) {
			subSchema = this.data.property("additionalProperties");
			if (subSchema.defined()) {
				schemas.push(subSchema.asSchema());
			}
		}
		return new SchemaList(schemas);
	},
	propertyDependencies: function (key) {
		var dependencies = this.data.property("dependencies");
		if (dependencies.defined()) {
			var dependency = dependencies.property(key);
			if (dependency.defined()) {
				if (dependency.basicType() == "string") {
					return [dependency.value()];
				} else if (dependency.basicType() == "array") {
					return dependency.value();
				} else {
					return [dependency.asSchema()];
				}
			}
		}
		return [];
	},
	indexSchemas: function (i) {
		var items = this.data.property("items");
		var subSchema;
		if (!items.defined()) {
			return new SchemaList();
		}
		if (items.basicType() == "array") {
			subSchema = items.index(i);
			if (!subSchema.defined()) {
				subSchema = this.data.property("additionalItems");
			}
		} else {
			subSchema = items;
		}
		if (subSchema.defined()) {
			var result = subSchema.asSchema();
			return new SchemaList([result]);
		}
		return new SchemaList();
	},
	andSchemas: function () {
		var result = [];
		var extData = this.data.property("extends");
		if (extData.defined()) {
			if (extData.basicType() == "array") {
				extData.indices(function (i, e) {
					result.push(e.asSchema());
				});
			} else {
				result.push(extData.asSchema());
			}
		}
		this.data.property("allOf").items(function (index, data) {
			result.push(data.asSchema());
		});
		return new SchemaList(result);
	},
	notSchemas: function () {
		var result = [];
		var disallowData = this.data.property("disallow");
		if (disallowData.defined()) {
			if (disallowData.basicType() == "array") {
				disallowData.indices(function (i, e) {
					if (e.basicType() == "string") {
						result.push(publicApi.createSchema({type: e.value()}));
					} else {
						result.push(e.asSchema());
					}
				});
			} else if (disallowData.basicType() == "string") {
				result.push(publicApi.createSchema({type: disallowData.value()}));
			} else {
				result.push(disallowData.asSchema());
			}
		}
		if (this.data.property("not").defined()) {
			result.push(this.data.property("not").asSchema());
		}
		return result;
	},
	types: function () {
		var typeData = this.data.property("type");
		if (typeData.defined()) {
			if (typeData.basicType() === "string") {
				if (typeData.value() == "all") {
					return ALL_TYPES.slice(0);
				}
				return [typeData.value()];
			} else {
				var types = [];
				for (var i = 0; i < typeData.length(); i++) {
					if (typeData.item(i).basicType() == "string") {
						if (typeData.item(i).value() == "all") {
							return ALL_TYPES.slice(0);
						}
						types.push(typeData.item(i).value());
					} else {
						return ALL_TYPES.slice(0);
					}
				}
				if (types.indexOf("number") != -1 && types.indexOf("integer") == -1) {
					types.push("integer");
				}
				return types;
			}
		}
		return ALL_TYPES.slice(0);
	},
	xorSchemas: function () {
		var result = [];
		var typeData = this.data.property("type");
		if (typeData.defined()) {
			for (var i = 0; i < typeData.length(); i++) {
				if (typeData.item(i).basicType() != "string") {
					var xorGroup = [];
					typeData.items(function (index, subData) {
						if (subData.basicType() == "string") {
							xorGroup.push(getTypeSchema(subData.value()));
						} else {
							xorGroup.push(subData.asSchema());
						}
					});
					result.push(xorGroup);
					break;
				}
			}
		}
		if (this.data.property("oneOf").defined()) {
			var xorGroup = [];
			this.data.property("oneOf").items(function (index, subData) {
				xorGroup.push(subData.asSchema());
			});
			result.push(xorGroup);
		}
		return result;
	},
	orSchemas: function () {
		var result = [];
		var typeData = this.data.property("type");
		if (this.data.property("anyOf").defined()) {
			var orGroup = [];
			this.data.property("anyOf").items(function (index, subData) {
				orGroup.push(subData.asSchema());
			});
			result.push(orGroup);
		}
		return result;
	},
	equals: function (otherSchema, resolveRef) {
		var thisSchema = this;
		if (resolveRef) {
			otherSchema = otherSchema.getFull();
			thisSchema = this.getFull();
		}
		if (thisSchema === otherSchema) {
			return true;
		}
		var thisRefUrl = thisSchema.referenceUrl();
		var otherRefUrl = otherSchema.referenceUrl();
		if (resolveRef && !thisSchema.isFull()) {
			thisRefUrl = thisSchema.data.resolveUrl(this.data.propertyValue("$ref"));
		}
		if (resolveRef && !otherSchema.isFull()) {
			otherRefUrl = otherSchema.data.resolveUrl(otherSchema.data.propertyValue("$ref"));
		}
		if (thisRefUrl !== undefined && otherRefUrl !== undefined) {
			return Utils.urlsEqual(thisRefUrl, otherRefUrl);
		}
		return this.data.equals(otherSchema.data);
	},
	enumValues: function () {
		return this.data.propertyValue("enum");
	},
	enumData: function () {
		return this.data.property("enum");
	},
	minItems: function () {
		var result = this.data.propertyValue("minItems");
		if (result == undefined) {
			return 0;
		}
		return result;
	},
	maxItems: function () {
		return this.data.propertyValue("maxItems");
	},
	tupleTypingLength: function () {
		if (this.data.property("items").basicType() != "array") {
			return 0;
		}
		return this.data.property("items").length();
	},
	minLength: function () {
		var result = this.data.propertyValue("minLength");
		if (result == undefined) {
			return 0;
		}
		return result;
	},
	maxLength: function () {
		return this.data.propertyValue("maxLength");
	},
	numberInterval: function() {
		return this.data.propertyValue("divisibleBy");
	},
	minimum: function () {
		return this.data.propertyValue("minimum");
	},
	exclusiveMinimum: function () {
		return !!this.data.propertyValue("exclusiveMinimum");
	},
	maximum: function () {
		return this.data.propertyValue("maximum");
	},
	exclusiveMaximum: function () {
		return !!this.data.propertyValue("exclusiveMaximum");
	},
	minProperties: function () {
		var result = this.data.propertyValue("minProperties");
		if (result == undefined) {
			return 0;
		}
		return result;
	},
	maxProperties: function () {
		return this.data.propertyValue("maxProperties");
	},
	definedProperties: function(ignoreList) {
		if (ignoreList) {
			this.definedProperties(); // created cached function
			return this.definedProperties(ignoreList);
		}
		var keys = this.data.property("properties").keys();
		this.definedProperties = function (ignoreList) {
			ignoreList = ignoreList || [];
			var result = [];
			for (var i = 0; i < keys.length; i++) {
				if (ignoreList.indexOf(keys[i]) == -1) {
					result.push(keys[i]);
				}
			}
			return result;
		};
		return keys.slice(0);
	},
	knownProperties: function(ignoreList) {
		if (ignoreList) {
			this.knownProperties(); // created cached function
			return this.knownProperties(ignoreList);
		}
		var result = {};
		this.data.property("properties").properties(function (key, subData) {
			result[key] = true;
		});
		var required = this.requiredProperties();
		for (var i = 0; i < required.length; i++) {
			result[required[i]] = true;
		}
		var keys = Object.keys(result);
		this.knownProperties = function (ignoreList) {
			ignoreList = ignoreList || [];
			var result = [];
			for (var i = 0; i < keys.length; i++) {
				if (ignoreList.indexOf(keys[i]) == -1) {
					result.push(keys[i]);
				}
			}
			return result;
		};
		return keys.slice(0);
	},
	requiredProperties: function () {
		var requiredKeys = this.data.propertyValue("required");
		if (typeof requiredKeys != "object") {
			requiredKeys = [];
		}
		var properties = this.data.property("properties");
		if (properties != undefined) {
			properties.properties(function (key, subData) {
				var required = subData.property("required");
				if (required != undefined && required.basicType() == "boolean" && required.value()) {
					requiredKeys.push(key);
				}
			});
		}
		return requiredKeys;
	},
	allowedAdditionalProperties: function () {
		return !(this.data.propertyValue("additionalProperties") === false);
	},
	getLink: function (rel) {
		var links = this.links();
		for (var i = 0; i < links.length; i++) {
			if (links[i].rel() == rel) {
				return links[i];
			}
		}
	},
	asList: function () {
		return new SchemaList([this]);
	},
	format: function () {
		return this.data.propertyValue("format");
	}
};
Schema.prototype.basicTypes = Schema.prototype.types;
Schema.prototype.extendSchemas = Schema.prototype.andSchemas;
Schema.prototype.isComplete = Schema.prototype.isFull;

publicApi.extendSchema = function (obj) {
	for (var key in obj) {
		if (Schema.prototype[key] == undefined) {
			Schema.prototype[key] = obj[key];
		}
	}
};

var extraEscaping = {
	"!": "%21",
	"'": "%27",
	"(": "%28",
	")": "%29",
	"*": "%2A"
};
function preProcessUriTemplate(template) {
	if (template == "{@}") {
		return "{+%73elf}";
	}
	var newTemplate = [];
	var curlyBrackets = false;
	var roundBrackets = false;
	for (var i = 0; i < template.length; i++) {
		var tChar = template.charAt(i);
		if (!curlyBrackets) {
			if (tChar == "{") {
				curlyBrackets = true;
			}
			newTemplate.push(tChar);
		} else if (!roundBrackets) {
			if (tChar == "$") {
				newTemplate.push("%73elf");
				continue;
			} else if (tChar == "(") {
				if (template.charAt(i + 1) == ")") {
					newTemplate.push("%65mpty");
					i++;
				} else {
					roundBrackets = true;
				}
				continue;
			} else if (tChar == "}") {
				curlyBrackets = false;
			}
			newTemplate.push(tChar);
		} else {
			if (tChar == ")") {
				if (template.charAt(i + 1) == ")") {
					newTemplate.push(extraEscaping[")"]);
					i++;
				} else {
					roundBrackets = false;
				}
				continue;
			}
			if (extraEscaping[tChar] != undefined) {
				newTemplate.push(extraEscaping[tChar])
			} else {
				newTemplate.push(encodeURIComponent(tChar));
			}
		}
	}
	return newTemplate.join("");
}

function PotentialLink(linkData) {
	this.data = linkData;
	
	this.uriTemplate = new UriTemplate(preProcessUriTemplate(linkData.propertyValue("href")));
	this.dataParts = [];
	for (var i = 0; i < this.uriTemplate.varNames.length; i++) {
		this.dataParts.push(translateUriTemplateName(this.uriTemplate.varNames[i]));
	}
	
	var schemaData = linkData.property("schema");
	if (schemaData.defined()) {
		var schema = schemaData.asSchema();
		this.submissionSchemas = new SchemaList([schema]);
	} else {
		this.submissionSchemas = new SchemaList();
	}
	var targetSchemaData = linkData.property("targetSchema");
	if (targetSchemaData.defined()) {
		this.targetSchema = targetSchemaData.asSchema();
	}
	
	this.handlers = [];
	this.preHandlers = [];
}
function translateUriTemplateName(varName) {
	if (varName == "%65mpty") {
		return "";
	} else if (varName == "%73elf") {
		return null;
	}
	return decodeURIComponent(varName);
}
PotentialLink.prototype = {
	addHandler: function(handler) {
		this.handlers.unshift(handler);
		return this;
	},
	addPreHandler: function(handler) {
		this.preHandlers.push(handler);
		return this;
	},
	canApplyTo: function (candidateData) {
		var i, key, subData = null, basicType;
		for (i = 0; i < this.dataParts.length; i++) {
			key = this.dataParts[i];
			if (key === null) {
				subData = candidateData;
			} else if (candidateData.basicType() == "object") {
				subData = candidateData.property(key);
			} else if (candidateData.basicType() == "array" && isIndex(key)) {
				subData = candidateData.index(key);
			}
			if (subData == undefined || !subData.defined()) {
				return false;
			}
			if (subData.basicType() == "null") {
				return false;
			}
		}
		return true;
	},
	linkForData: function (publicData) {
		var rawLink = this.data.value();
		var href = this.uriTemplate.fill(function (varName) {
			varName = translateUriTemplateName(varName);
			if (varName == null) {
				return publicData.value();
			}
			if (publicData.basicType() == "array") {
				return publicData.itemValue(varName);
			} else {
				return publicData.propertyValue(varName);
			}
		});
		rawLink.href = publicData.resolveUrl(href);
		rawLink.rel = rawLink.rel.toLowerCase();
		return new ActiveLink(rawLink, this, publicData);
	},
	usesKey: function (key) {
		var i;
		for (i = 0; i < this.dataParts.length; i++) {
			if (this.dataParts[i] === key) {
				return true;
			}
		}
		return false;
	},
	rel: function () {
		return this.data.propertyValue("rel").toLowerCase();
	}
};

var defaultLinkHandlers = [];
var defaultLinkPreHandlers = [];
publicApi.addLinkHandler = function(handler) {
	defaultLinkHandlers.unshift(handler);
};
publicApi.addLinkPreHandler = function(handler) {
	defaultLinkPreHandlers.push(handler);
};

function ActiveLink(rawLink, potentialLink, data) {
	this.rawLink = rawLink;
	this.definition = potentialLink;
	this.subjectData = data;

	this.href = rawLink.href;
	var hashIndex = this.href.indexOf('#');
	if (hashIndex >= 0) {
		this.hrefBase = this.href.substring(0, hashIndex);
		this.hrefFragment = this.href.substring(hashIndex + 1);
	} else {
		this.hrefBase = this.href;
		this.hrefFragment = "";
	}

	this.rel = rawLink.rel;
	if (rawLink.method != undefined) {
		this.method = rawLink.method;
	} else if (rawLink.rel == "edit") {
		this.method = "PUT"
	} else if (rawLink.rel == "create") {
		this.method = "POST"
	} else if (rawLink.rel == "delete") {
		this.method = "DELETE"
	} else {
		this.method = "GET";
	}
	if (rawLink.enctype != undefined) {
		rawLink.encType = rawLink.enctype;
		delete rawLink.enctype;
	}
	if (rawLink.encType == undefined) {
		if (this.method == "GET") {
			this.encType = "application/x-www-form-urlencoded";
		} else if (this.method == "POST" || this.method == "PUT") {
			this.encType = "application/json";
		} else {
			this.encType = "application/x-www-form-urlencoded";
		}
	} else {
		this.encType = rawLink.encType;
	}
	if (this.definition != null) {
		this.submissionSchemas = this.definition.submissionSchemas;
		this.targetSchema = this.definition.targetSchema;
	}
}
var ACTIVE_LINK_SCHEMA_KEY = Utils.getUniqueKey();
ActiveLink.prototype = {
	toString: function() {
		return this.href;
	},
	createSubmissionData: function(callback) {
		var hrefBase = this.hrefBase;
		var submissionSchemas = this.submissionSchemas;
		if (callback != undefined && submissionSchemas.length == 0 && this.method == "PUT") {
			Jsonary.getData(this.href, function (data) {
				callback(data.editableCopy());
			})
			return this;
		}
		if (callback != undefined) {
			submissionSchemas.createValue(function (value) {
				var data = publicApi.create(value, hrefBase);
				for (var i = 0; i < submissionSchemas.length; i++) {
					data.addSchema(submissionSchemas[i], ACTIVE_LINK_SCHEMA_KEY);
				}
				callback(data);
			});
		} else {
			var value = submissionSchemas.createValue();
			var data = publicApi.create(value, hrefBase);
			for (var i = 0; i < submissionSchemas.length; i++) {
				data.addSchema(submissionSchemas[i], ACTIVE_LINK_SCHEMA_KEY);
			}
			return data;
		}
	},
	follow: function(submissionData, extraHandler) {
		if (typeof submissionData == 'function') {
			extraHandler = submissionData;
			submissionData = undefined;
		}
		if (submissionData !== undefined) {
			if (!(submissionData instanceof Data)) {
				submissionData = publicApi.create(submissionData);
			}
		} else {
			submissionData = publicApi.create(undefined);
		}
		var preHandlers = defaultLinkPreHandlers.concat(this.definition.preHandlers);
		for (var i = 0; i < preHandlers.length; i++) {
			var handler = preHandlers[i];
			if (handler.call(this, this, submissionData) === false) {
				Utils.log(Utils.logLevel.DEBUG, "Link cancelled: " + this.href);
				return null;
			}
		}
		var value = submissionData.value();
		
		var request = publicApi.getData({
			url:this.href,
			method:this.method,
			data:value,
			encType:this.encType
		}, null, this.targetSchema);
		submissionData = submissionData.readOnlyCopy();
		var handlers = this.definition.handlers.concat(defaultLinkHandlers);
		if (extraHandler !== undefined) {
			handlers.unshift(extraHandler);
		}
		for (var i = 0; i < handlers.length; i++) {
			var handler = handlers[i];
			if (handler.call(this, this, submissionData, request) === false) {
				break;
			}
		}
		return request;
	}
};


function SchemaMatch(monitorKey, data, schema, impatientCallbacks) {
	var thisSchemaMatch = this;
	this.monitorKey = monitorKey;
	this.match = false;
	this.matchFailReason = new SchemaMatchFailReason("initial failure", null);
	this.monitors = new MonitorSet(schema);
	this.impatientCallbacks = impatientCallbacks;
	
	this.propertyMatches = {};
	this.indexMatches = {};

	this.dependencies = {};
	this.dependencyKeys = {};

	this.schemaLoaded = false;
	this.data = data;
	schema.getFull(function (schema) {
		thisSchemaMatch.schemaLoaded = true;
		thisSchemaMatch.schema = schema;

		thisSchemaMatch.basicTypes = schema.basicTypes();
		thisSchemaMatch.setupXorSelectors();
		thisSchemaMatch.setupOrSelectors();
		thisSchemaMatch.setupAndMatches();
		thisSchemaMatch.setupNotMatches();
		thisSchemaMatch.dataUpdated();
	});
}
SchemaMatch.prototype = {
	setupXorSelectors: function () {
		var thisSchemaMatch = this;
		this.xorSelectors = {};
		var xorSchemas = this.schema.xorSchemas();
		for (var i = 0; i < xorSchemas.length; i++) {
			var xorSelector = new XorSelector(Utils.getKeyVariant(this.monitorKey, "xor" + i), xorSchemas[i], this.data);
			this.xorSelectors[i] = xorSelector;
			xorSelector.onMatchChange(function (selectedOption) {
				thisSchemaMatch.update();
			}, false);
		}
	},
	setupOrSelectors: function () {
		var thisSchemaMatch = this;
		this.orSelectors = {};
		var orSchemas = this.schema.orSchemas();
		for (var i = 0; i < orSchemas.length; i++) {
			var orSelector = new OrSelector(Utils.getKeyVariant(this.monitorKey, "or" + i), orSchemas[i], this.data);
			this.orSelectors[i] = orSelector;
			orSelector.onMatchChange(function (selectedOptions) {
				thisSchemaMatch.update();
			}, false);
		}
	},
	setupAndMatches: function () {
		var thisSchemaMatch = this;
		this.andMatches = [];
		var andSchemas = this.schema.andSchemas();
		andSchemas.each(function (index, subSchema) {
			var keyVariant = Utils.getKeyVariant(thisSchemaMatch.monitorKey, "and" + index);
			var subMatch = thisSchemaMatch.data.addSchemaMatchMonitor(keyVariant, subSchema, function () {
				thisSchemaMatch.update();
			}, false, true);
			thisSchemaMatch.andMatches.push(subMatch);
		});
	},
	setupNotMatches: function () {
		var thisSchemaMatch = this;
		this.notMatches = [];
		var notSchemas = this.schema.notSchemas();
		for (var i = 0; i < notSchemas.length; i++) {
			(function (index, subSchema) {
				var keyVariant = Utils.getKeyVariant(thisSchemaMatch.monitorKey, "not" + index);
				var subMatch = thisSchemaMatch.data.addSchemaMatchMonitor(keyVariant, subSchema, function () {
					thisSchemaMatch.update();
				}, false, true);
				thisSchemaMatch.notMatches.push(subMatch);
			})(i, notSchemas[i]);
		}
	},
	addMonitor: function (monitor, executeImmediately) {
		// TODO: make a monitor set that doesn't require keys.  The keyed one could use it!
		this.monitors.add(this.monitorKey, monitor);
		if (executeImmediately !== false) {
			monitor.call(this.schema, this.match, this.matchFailReason);
		}
		return this;
	},
	dataUpdated: function (key) {
		if (!this.schemaLoaded) {
			return;
		}
		var thisSchemaMatch = this;
		if (this.data.basicType() == "object") {
			this.indexMatches = {};
			this.data.properties(function (key, subData) {
				if (thisSchemaMatch.propertyMatches[key] == undefined) {
					var matches = [];
					var subSchemas = thisSchemaMatch.schema.propertySchemas(key);
					subSchemas.each(function (i, subSchema) {
						var subMatch = subData.addSchemaMatchMonitor(thisSchemaMatch.monitorKey, subSchemas[i], function () {
							thisSchemaMatch.subMatchUpdated(key, subMatch);
						}, false, true);
						matches.push(subMatch);
					});
					thisSchemaMatch.propertyMatches[key] = matches;
					thisSchemaMatch.addDependencies(key);
				}
			});
			var keysToRemove = [];
			for (var key in this.propertyMatches) {
				if (!this.data.property(key).defined()) {
					keysToRemove.push(key);
				}
			};
			for (var i = 0; i < keysToRemove.length; i++) {
				var key = keysToRemove[i];
				delete this.propertyMatches[key];
				if (this.dependencyKeys[key] != undefined) {
					this.data.removeSchema(this.dependencyKeys[key]);
					delete this.dependencies[key];
					delete this.dependencyKeys[key];
				}
			}
		} else if (this.data.basicType() == "array") {
			this.propertyMatches = {};
			this.data.indices(function (index, subData) {
				if (thisSchemaMatch.indexMatches[index] == undefined) {
					var matches = [];
					var subSchemas = thisSchemaMatch.schema.indexSchemas(index);
					subSchemas.each(function (i, subSchema) {
						var subMatch = subData.addSchemaMatchMonitor(thisSchemaMatch.monitorKey, subSchemas[i], function () {
							thisSchemaMatch.subMatchUpdated(key, subMatch);
						}, false, true);
						matches.push(subMatch);
					});
					thisSchemaMatch.indexMatches[index] = matches;
				}
			});
			var keysToRemove = [];
			for (var key in this.indexMatches) {
				if (this.data.length() <= key) {
					keysToRemove.push(key);
				}
			};
			for (var i = 0; i < keysToRemove.length; i++) {
				delete this.indexMatches[keysToRemove[i]];
			}
		} else {
			this.propertyMatches = {};
			this.indexMatches = {};
		}
		this.update();
	},
	addDependencies: function (key) {
		var thisSchemaMatch = this;
		var dependencies = this.schema.propertyDependencies(key);
		this.dependencies[key] = [];
		this.dependencyKeys[key] = [];
		for (var i = 0; i < dependencies.length; i++) {
			var dependency = dependencies[i];
			if (typeof (dependency) == "string") {
				this.dependencies[key].push(dependency);
			} else {
				(function (index) {
					var subMonitorKey = Utils.getKeyVariant(thisSchemaMatch.monitorKey, "dep:" + key + ":" + index);
					thisSchemaMatch.dependencyKeys[key].push(subMonitorKey);
					var subMatch = thisSchemaMatch.data.addSchemaMatchMonitor(subMonitorKey, dependency, function () {
						thisSchemaMatch.dependencyUpdated(key, index);
					}, false, true);
					thisSchemaMatch.dependencies[key].push(subMatch);
				})(i);
			}
		}
	},
	notify: function () {
		this.monitors.notify(this.match, this.matchFailReason);
	},
	setMatch: function (match, failReason) {
		var thisMatch = this;
		var oldMatch = this.match;
		var oldFailReason = this.matchFailReason;
		
		this.match = match;
		if (!match) {
			this.matchFailReason = failReason;
		} else {
			this.matchFailReason = null;
		}
		if (this.impatientCallbacks) {
			return this.notify();
		}
		
		if (this.pendingNotify) {
			return;
		}
		this.pendingNotify = true;
		DelayedCallbacks.add(function () {
			thisMatch.pendingNotify = false;
			if (thisMatch.match && oldMatch) {
				// Still matches - no problem
				return;
			}
			if (!thisMatch.match && !oldMatch && thisMatch.matchFailReason.equals(oldFailReason)) {
				// Still failing for the same reason
				return;
			}
			thisMatch.notify();
		});
	},	subMatchUpdated: function (indexKey, subMatch) {
		this.update();
	},
	subMatchRemoved: function (indexKey, subMatch) {
		this.update();
	},
	dependencyUpdated: function (key, index) {
		this.update();
	},
	update: function () {
		try {
			this.matchAgainstBasicTypes();
			this.matchAgainstSubMatches();
			this.matchAgainstImmediateConstraints();
			this.setMatch(true);
		} catch (exception) {
			if (exception instanceof SchemaMatchFailReason) {
				this.setMatch(false, exception);
			} else {
				throw exception;
			}
		}
	},
	matchAgainstBasicTypes: function () {
		var basicType = this.data.basicType();
		for (var i = 0; i < this.basicTypes.length; i++) {
			if (this.basicTypes[i] == basicType || basicType == "integer" && this.basicTypes[i] == "number") {
				return;
			}
		}
		throw new SchemaMatchFailReason("Data does not match any of the basic types: " + this.basicTypes, this.schema);
	},
	matchAgainstSubMatches: function () {
		for (var i = 0; i < this.andMatches.length; i++) {
			var andMatch = this.andMatches[i];
			if (!andMatch.match) {
				var message = "extended schema #" + i + ": " + andMatch.message;
				throw new SchemaMatchFailReason(message, this.schema, andMatch.failReason);
			}
		}
		for (var i = 0; i < this.notMatches.length; i++) {
			var notMatch = this.notMatches[i];
			if (notMatch.match) {
				var message = "\"not\" schema #" + i + " matches";
				throw new SchemaMatchFailReason(message, this.schema);
			}
		}
		for (var key in this.xorSelectors) {
			var selector = this.xorSelectors[key];
			if (selector.selectedOption == null) {
				var message = "XOR #" + key + ": " + selector.failReason.message;
				throw new SchemaMatchFailReason(message, this.schema, selector.failReason);
			}
		}
		for (var key in this.orSelectors) {
			var selector = this.orSelectors[key];
			if (selector.selectedOptions.length == 0) {
				var message = "OR #" + key + ": no matches";
				throw new SchemaMatchFailReason(message, this.schema);
			}
		}
		for (var key in this.propertyMatches) {
			var subMatchList = this.propertyMatches[key];
			for (var i = 0; i < subMatchList.length; i++) {
				var subMatch = subMatchList[i];
				if (!subMatch.match) {
					var message = key + ": " + subMatch.matchFailReason.message;
					throw new SchemaMatchFailReason(message, this.schema, subMatch.matchFailReason);
				}
			}
		}
		for (var key in this.indexMatches) {
			var subMatchList = this.indexMatches[key];
			for (var i = 0; i < subMatchList.length; i++) {
				var subMatch = subMatchList[i];
				if (!subMatch.match) {
					var message = key + ": " + subMatch.matchFailReason.message;
					throw new SchemaMatchFailReason(message, this.schema, subMatch.matchFailReason);
				}
			}
		}
	},
	matchAgainstImmediateConstraints: function () {
		this.matchAgainstEnums();
		this.matchAgainstNumberConstraints();
		this.matchAgainstArrayConstraints();
		this.matchAgainstObjectConstraints();
	},
	matchAgainstEnums: function () {
		var enumList = this.schema.enumData();
		if (enumList.defined()) {
			for (var i = 0; i < enumList.length(); i++) {
				var enumValue = enumList.index(i);
				if (enumValue.equals(this.data)) {
					return;
				}
			}
			throw new SchemaMatchFailReason("Data does not match enum: " + JSON.stringify(enumList.value()) + " (" + JSON.stringify(this.data.value()) + ")", this.schema);
		}
	},
	matchAgainstNumberConstraints: function () {
		if (this.data.basicType() != "number" && this.data.basicType() != "integer") {
			return;
		}
		var value = this.data.value();
		var interval = this.schema.numberInterval();
		if (interval != undefined) {
			if (value%interval != 0) {
				throw new SchemaMatchFailReason("Number must be divisible by " + interval);
			}
		}
		var minimum = this.schema.minimum();
		if (minimum !== undefined) {
			if (this.schema.exclusiveMinimum()) {
				if (value <= minimum) {
					throw new SchemaMatchFailReason("Number must be > " + minimum);
				}
			} else if (value < minimum) {
				throw new SchemaMatchFailReason("Number must be >= " + minimum);
			}
		}
		var maximum = this.schema.maximum();
		if (maximum != undefined) {
			if (this.schema.exclusiveMaximum()) {
				if (value >= maximum) {
					throw new SchemaMatchFailReason("Number must be < " + maximum);
				}
			} else if (value > maximum) {
				throw new SchemaMatchFailReason("Number must be <= " + maximum);
			}
		}
	},
	matchAgainstArrayConstraints: function () {
		if (this.data.basicType() != "array") {
			return;
		}
		var minItems = this.schema.minItems();
		if (minItems !== undefined && minItems > this.data.length()) {
			throw new SchemaMatchFailReason("Data is not long enough - minimum length is " + minItems, this.schema);
		}
		var maxItems = this.schema.maxItems();
		if (maxItems !== undefined && maxItems < this.data.length()) {
			throw new SchemaMatchFailReason("Data is too long - maximum length is " + maxItems, this.schema);
		}
	},
	matchAgainstObjectConstraints: function () {
		if (this.data.basicType() != "object") {
			return;
		}
		var required = this.schema.requiredProperties();
		for (var i = 0; i < required.length; i++) {
			var key = required[i];
			if (!this.data.property(key).defined()) {
				throw new SchemaMatchFailReason("Missing key " + JSON.stringify(key), this.schema);
			}
		}
		if (this.schema.allowedAdditionalProperties() == false) {
			var definedKeys = this.schema.definedProperties();
			var dataKeys = this.data.keys();
			for (var i = 0; i < dataKeys.length; i++) {
				if (definedKeys.indexOf(dataKeys[i]) == -1) {
					throw new SchemaMatchFailReason("Not allowed additional property: " + JSON.stringify(key), this.schema);
				}
			}
		}
		this.matchAgainstDependencies();
	},
	matchAgainstDependencies: function () {
		for (var key in this.dependencies) {
			if (this.data.property(key) == undefined) {
				continue;
			}
			var dependencyList = this.dependencies[key];
			for (var i = 0; i < dependencyList.length; i++) {
				var dependency = dependencyList[i];
				if (typeof dependency == "string") {
					if (!this.data.property(dependency).defined()) {
						throw new SchemaMatchFailReason("Dependency - property " + JSON.stringify(key) + " requires property " + JSON.stringify(dependency), this.schema);
					}
				} else {
					if (!dependency.match) {
						throw new SchemaMatchFailReason("Dependency for " + key, this.schema, dependency.matchFailReason);
					}
				}
			}
		}
	}
};

function SchemaMatchFailReason(message, schema, subMatchFailReason) {
	this.message = message;
	this.schema = schema;
	this.subMatchFailReason = subMatchFailReason;
}
SchemaMatchFailReason.prototype = new Error();
SchemaMatchFailReason.prototype.toString = function () {
	return this.message + " in " + this.schema.title();
};
SchemaMatchFailReason.prototype.equals = function (other) {
	if (!(other instanceof SchemaMatchFailReason)) {
		return false;
	}
	if (this.subMatchFailReason == null) {
		if (other.subMatchFailReason != null) {
			return false;
		}
	} else if (other.subMatchFailReason == null || !this.subMatchFailReason.equals(other.subMatchFailReason)) {
		return false;
	}
	return this.message == other.message && (this.schema == null && other.schema == null || this.schema != null && other.schema != null && this.schema.equals(other.schema));
};

function XorSelector(schemaKey, options, dataObj) {
	var thisXorSelector = this;
	this.options = options;
	this.matchCallback = null;
	this.selectedOption = null;
	this.data = dataObj;
	
	this.subMatches = [];
	this.subSchemaKeys = [];
	var pendingUpdate = false;
	for (var i = 0; i < options.length; i++) {
		this.subSchemaKeys[i] = Utils.getKeyVariant(schemaKey, "option" + i);
		this.subMatches[i] = dataObj.addSchemaMatchMonitor(this.subSchemaKeys[i], options[i], function () {
			thisXorSelector.update();
		}, false, true);
	}
	this.update();
}
XorSelector.prototype = {
	onMatchChange: function (callback, executeImmediately) {
		this.matchCallback = callback;
		if (executeImmediately !== false) {
			callback.call(this, this.selectedOption);
		}
		return this;
	},
	update: function () {
		var nextOption = null;
		var failReason = "No matches";
		for (var i = 0; i < this.subMatches.length; i++) {
			if (this.subMatches[i].match) {
				if (nextOption == null) {
					nextOption = this.options[i];
					failReason = null;
				} else {
					failReason = "multiple matches";
					nextOption = null;
					break;
				}
			}
		}
		this.failReason = new SchemaMatchFailReason(failReason);
		if (this.selectedOption != nextOption) {
			this.selectedOption = nextOption;
			if (this.matchCallback != undefined) {
				this.matchCallback.call(this, this.selectedOption);
			}
		}
	}
};

function OrSelector(schemaKey, options, dataObj) {
	var thisOrSelector = this;
	this.options = options;
	this.matchCallback = null;
	this.selectedOptions = [];
	this.data = dataObj;
	
	this.subMatches = [];
	this.subSchemaKeys = [];
	var pendingUpdate = false;
	for (var i = 0; i < options.length; i++) {
		this.subSchemaKeys[i] = Utils.getKeyVariant(schemaKey, "option" + i);
		this.subMatches[i] = dataObj.addSchemaMatchMonitor(this.subSchemaKeys[i], options[i], function () {
			thisOrSelector.update();
		}, false, true);
	}
	this.update();
}
OrSelector.prototype = {
	onMatchChange: function (callback, executeImmediately) {
		this.matchCallback = callback;
		if (executeImmediately !== false) {
			callback.call(this, this.selectedOptions);
		}
		return this;
	},
	update: function () {
		var nextOptions = [];
		var failReason = "No matches";
		for (var i = 0; i < this.subMatches.length; i++) {
			if (this.subMatches[i].match) {
				nextOptions.push(this.options[i]);
			}
		}
		var difference = false;
		if (nextOptions.length != this.selectedOptions.length) {
			difference = true;
		} else {
			for (var i = 0; i < nextOptions.length; i++) {
				if (nextOptions[i] != this.selectedOptions[i]) {
					difference = true;
					break;
				}
			}
		}
		if (difference) {
			this.selectedOptions = nextOptions;
			if (this.matchCallback != undefined) {
				this.matchCallback.call(this, this.selectedOptions);
			}
		}
	}
};

var schemaChangeListeners = [];
publicApi.registerSchemaChangeListener = function (listener) {
	schemaChangeListeners.push(listener);
};
var schemaChanges = {
};
var schemaNotifyPending = false;
function notifyAllSchemaChanges() {
	schemaNotifyPending = false;
	var dataEntries = [];
	for (var uniqueId in schemaChanges) {
		var data = schemaChanges[uniqueId];
		dataEntries.push({
			data: data,
			pointerPath: data.pointerPath()
		});
	}
	schemaChanges = {};
	dataEntries.sort(function (a, b) {
		return a.pointerPath.length - b.pointerPath.length;
	});
	var dataObjects = [];
	for (var i = 0; i < dataEntries.length; i++) {
		dataObjects[i] = dataEntries[i].data;
	}
	for (var i = 0; i < schemaChangeListeners.length; i++) {
		schemaChangeListeners[i].call(null, dataObjects);
	}
}
function notifySchemaChangeListeners(data) {
	schemaChanges[data.uniqueId] = data;
	if (!schemaNotifyPending) {
		schemaNotifyPending = true;
		DelayedCallbacks.add(notifyAllSchemaChanges);
	}
}

function LinkList(linkList) {
	for (var i = 0; i < linkList.length; i++) {
		this[i] = linkList[i];
	}
	this.length = linkList.length;
}
LinkList.prototype = {
	rel: function(rel) {
		if (rel == undefined) {
			return this;
		}
		var result = [];
		var i;
		for (i = 0; i < this.length; i++) {
			if (this[i].rel === rel) {
				result[result.length] = this[i];
			}
		}
		return new LinkList(result);
	}
};

// TODO: see how many calls to dataObj can be changed to just use this object
function SchemaList(schemaList, fixedList) {
	if (schemaList == undefined) {
		this.length = 0;
		return;
	}
	if (fixedList == undefined) {
		fixedList = schemaList;
	}
	this.fixed = function () {
		var fixedSchemaList = (fixedList.length < schemaList.length) ? new SchemaList(fixedList) : this;
		this.fixed = function () {
			return fixedSchemaList;
		};
		return fixedSchemaList;
	};
	var i;
	for (i = 0; i < schemaList.length; i++) {
		this[i] = schemaList[i];
	}
	this.length = schemaList.length;
}
var ALL_TYPES_DICT = {
	"null": true,
	"boolean": true,
	"integer": true,
	"number": true,
	"string": true,
	"array": true,
	"object": true
};
SchemaList.prototype = {
	indexOf: function (schema, resolveRef) {
		var i = this.length - 1;
		while (i >= 0) {
			if (schema.equals(this[i], resolveRef)) {
				return i;
			}
			i--;
		}
		return i;
	},
	containsUrl: function(url) {
		if (url instanceof RegExp) {
			for (var i = 0; i < this.length; i++) {
				var schema = this[i];
				if (url.test(schema.referenceUrl())) {
					return true;
				}
			}
		} else {
			if (url.indexOf('#') < 0) {
				url += "#";
			}
			for (var i = 0; i < this.length; i++) {
				var schema = this[i];
				var referenceUrl = schema.referenceUrl();
				if (referenceUrl != null && referenceUrl.substring(referenceUrl.length - url.length) == url) {
					return true;
				}
			}
		}
		return false;
	},
	links: function () {
		var result = [];
		var i, schema;
		for (i = 0; i < this.length; i++) {
			schema = this[i];
			result = result.concat(schema.links());
		}
		return result;
	},
	each: function (callback) {
		for (var i = 0; i < this.length; i++) {
			callback.call(this, i, this[i]);
		}
		return this;
	},
	concat: function(other) {
		var newList = [];
		for (var i = 0; i < this.length; i++) {
			newList.push(this[i]);
		}
		for (var i = 0; i < other.length; i++) {
			newList.push(other[i]);
		}
		return new SchemaList(newList);
	},
	definedProperties: function (ignoreList) {
		if (ignoreList) {
			this.definedProperties(); // create cached function
			return this.definedProperties(ignoreList);
		}
		var additionalProperties = true;
		var definedKeys = {};
		this.each(function (index, schema) {
			if (additionalProperties) {
				if (!schema.allowedAdditionalProperties()) {
					additionalProperties = false;
					definedKeys = {};
				}
				var definedProperties = schema.definedProperties();
				for (var i = 0; i < definedProperties.length; i++) {
					definedKeys[definedProperties[i]] = true;
				}
			} else {
				if (!schema.allowedAdditionalProperties()) {
					additionalProperties = false;
					var newKeys = {};
					var definedProperties = schema.definedProperties();
					for (var i = 0; i < definedProperties.length; i++) {
						if (definedKeys[definedProperties[i]]) {
							newKeys[definedProperties[i]] = true;
						}
					}
					definedKeys = newKeys;
				}
			}
		});
		var result = Object.keys(definedKeys);
		cacheResult(this, {
			allowedAdditionalProperties: additionalProperties
		});
		this.definedProperties = function (ignoreList) {
			ignoreList = ignoreList || [];
			var newList = [];
			for (var i = 0; i < result.length; i++) {
				if (ignoreList.indexOf(result[i]) == -1) {
					newList.push(result[i]);
				}
			}
			return newList;
		};
		return result;
	},
	knownProperties: function (ignoreList) {
		if (ignoreList) {
			this.knownProperties(); // create cached function
			return this.knownProperties(ignoreList);
		}
		var result;
		if (this.allowedAdditionalProperties()) {
			result = this.definedProperties().slice(0);
			var requiredProperties = this.requiredProperties();
			for (var i = 0; i < requiredProperties.length; i++) {
				if (result.indexOf(requiredProperties[i]) == -1) {
					result.push(requiredProperties[i]);
				}
			}
		} else {
			var result = this.definedProperties();
		}
		this.knownProperties = function (ignoreList) {
			ignoreList = ignoreList || [];
			var newList = [];
			for (var i = 0; i < result.length; i++) {
				if (ignoreList.indexOf(result[i]) == -1) {
					newList.push(result[i]);
				}
			}
			return newList;
		};
		return result.slice(0);
	},
	allowedAdditionalProperties: function () {
		var additionalProperties = true;
		this.each(function (index, schema) {
			additionalProperties = (additionalProperties && schema.allowedAdditionalProperties());
		});
		cacheResult(this, {
			additionalProperties: additionalProperties
		});
		return additionalProperties;
	},
	minProperties: function () {
		var minProperties = 0;
		for (var i = 0; i < this.length; i++) {
			var otherMinProperties = this[i].minProperties();
			if (otherMinProperties > minProperties) {
				minProperties = otherMinProperties;
			}
		}
		return minProperties;
	},
	maxProperties: function () {
		var maxProperties = undefined;
		for (var i = 0; i < this.length; i++) {
			var otherMaxProperties = this[i].maxProperties();
			if (!(otherMaxProperties > maxProperties)) {
				maxProperties = otherMaxProperties;
			}
		}
		return maxProperties;
	},
	types: function () {
		var basicTypes = ALL_TYPES_DICT;
		for (var i = 0; i < this.length; i++) {
			var otherBasicTypes = this[i].basicTypes();
			var newBasicTypes = {};
			for (var j = 0; j < otherBasicTypes.length; j++) {
				var type = otherBasicTypes[j];
				if (basicTypes[type]) {
					newBasicTypes[type] = true;
				}
			}
			basicTypes = newBasicTypes;
		}
		return Object.keys(basicTypes);
	},
	numberInterval: function() {
		var candidate = undefined;
		for (var i = 0; i < this.length; i++) {
			var interval = this[i].numberInterval();
			if (interval == undefined) {
				continue;
			}
			if (candidate == undefined) {
				candidate = interval;
			} else {
				candidate = Utils.lcm(candidate, interval);
			}
		}
		for (var i = 0; i < this.length; i++) {
			var basicTypes = this[i].basicTypes();
			var hasInteger = false;
			for (var j = 0; j < basicTypes.length; j++) {
				if (basicTypes[j] == "number") {
					hasInteger = false;
					break;
				} else if (basicTypes[j] == "integer") {
					hasInteger = true;
				}
			}
			if (hasInteger) {
				if (candidate == undefined) {
					return 1;
				} else {
					return Utils.lcm(candidate, 1);
				}
			}
		}
		cacheResult(this, {
			numberInterval: candidate
		});
		return candidate;
	},
	minimum: function () {
		var minimum = undefined;
		var exclusive = false;
		for (var i = 0; i < this.length; i++) {
			var otherMinimum = this[i].minimum();
			if (otherMinimum != undefined) {
				if (minimum == undefined || minimum < otherMinimum) {
					minimum = otherMinimum;
					exclusive = this[i].exclusiveMinimum();
				}
			}
		}
		cacheResult(this, {
			minimum: minimum,
			exclusiveMinimum: exclusive
		});
		return minimum;
	},
	exclusiveMinimum: function () {
		this.minimum();
		return this.exclusiveMinimum();
	},
	maximum: function () {
		var maximum = undefined;
		var exclusive = false;
		for (var i = 0; i < this.length; i++) {
			var otherMaximum = this[i].maximum();
			if (otherMaximum != undefined) {
				if (maximum == undefined || maximum > otherMaximum) {
					maximum = otherMaximum;
					exclusive = this[i].exclusiveMaximum();
				}
			}
		}
		cacheResult(this, {
			maximum: maximum,
			exclusiveMaximum: exclusive
		});
		return maximum;
	},
	exclusiveMaximum: function () {
		this.minimum();
		return this.exclusiveMinimum();
	},
	minLength: function () {
		var minLength = 0;
		for (var i = 0; i < this.length; i++) {
			var otherMinLength = this[i].minLength();
			if (otherMinLength > minLength) {
				minLength = otherMinLength;
			}
		}
		cacheResult(this, {
			minLength: minLength
		});
		return minLength;
	},
	maxLength: function () {
		var maxLength = undefined;
		for (var i = 0; i < this.length; i++) {
			var otherMaxLength = this[i].maxLength();
			if (!(otherMaxLength > maxLength)) {
				maxLength = otherMaxLength;
			}
		}
		cacheResult(this, {
			maxLength: maxLength
		});
		return maxLength;
	},
	minItems: function () {
		var minItems = 0;
		for (var i = 0; i < this.length; i++) {
			var otherMinItems = this[i].minItems();
			if (otherMinItems > minItems) {
				minItems = otherMinItems;
			}
		}
		cacheResult(this, {
			minItems: minItems
		});
		return minItems;
	},
	maxItems: function () {
		var maxItems = undefined;
		for (var i = 0; i < this.length; i++) {
			var otherMaxItems = this[i].maxItems();
			if (!(otherMaxItems > maxItems)) {
				maxItems = otherMaxItems;
			}
		}
		cacheResult(this, {
			maxItems: maxItems
		});
		return maxItems;
	},
	tupleTypingLength: function () {
		var maxTuple = 0;
		for (var i = 0; i < this.length; i++) {
			var otherTuple = this[i].tupleTypingLength();
			if (otherTuple > maxTuple) {
				maxTuple = otherTuple;
			}
		}
		return maxTuple;
	},
	requiredProperties: function () {
		var required = {};
		var requiredList = [];
		for (var i = 0; i < this.length; i++) {
			var requiredProperties = this[i].requiredProperties();
			for (var j = 0; j < requiredProperties.length; j++) {
				var key = requiredProperties[j];
				if (!required[key]) {
					required[key] = true;
					requiredList.push(key);
				}
			}
		}
		return requiredList;
	},
	enumValues: function () {
		var enums = undefined;
		for (var i = 0; i < this.length; i++) {
			var enumData = this[i].enumData();
			if (enumData.defined()) {
				if (enums == undefined) {
					enums = [];
					enumData.indices(function (index, subData) {
						enums[index] = subData;
					});
				} else {
					var newEnums = [];
					enumData.indices(function (index, subData) {
						for (var i = 0; i < enums.length; i++) {
							if (enums[i].equals(subData)) {
								newEnums.push(subData);
							}
						}
					});
					enums = newEnums;
				}
			}
		}
		if (enums != undefined) {
			var values = [];
			for (var i = 0; i < enums.length; i++) {
				values[i] = enums[i].value();
			}
			return values;
		}
	},
	allCombinations: function (callback) {
		if (callback && !this.isFull()) {
			this.getFull(function (full) {
				full.allCombinations(callback);
			});
			return [];
		}
		var thisSchemaSet = this;
		// This is a little inefficient
		var xorSchemas = this.xorSchemas();
		for (var i = 0; i < xorSchemas.length; i++) {
			var found = false;
			for (var optionNum = 0; optionNum < xorSchemas[i].length; optionNum++) {
				var option = xorSchemas[i][optionNum];
				if (this.indexOf(option, !!callback) >= 0) {
					found = true;
					break;
				}
			}
			if (!found) {
				var result = [];
				var pending = 1;
				var gotResult = function() {
					pending--;
					if (pending <= 0) {
						callback(result);
					}
				};
				for (var optionNum = 0; optionNum < xorSchemas[i].length; optionNum++) {
					var option = xorSchemas[i][optionNum];
					if (callback) {
						pending++;
						this.concat([option]).allCombinations(function (subCombos) {
							result = result.concat(subCombos);
							gotResult();
						});
					} else {
						var subCombos = this.concat([option]).allCombinations();
						result = result.concat(subCombos);
					}
				}
				if (callback) {
					gotResult();
				}
				return result;
			}
		}
		
		var orSchemas = this.orSchemas();
		var totalCombos = null;
		var orSelectionOptionSets = [];
		var orPending = 1;
		function gotOrResult() {
			orPending--;
			if (orPending <= 0) {
				var totalCombos = [new SchemaList([])];
				for (var optionSetIndex = 0; optionSetIndex < orSelectionOptionSets.length; optionSetIndex++) {
					var optionSet = orSelectionOptionSets[optionSetIndex];
					var newTotalCombos = [];
					for (var optionIndex = 0; optionIndex < optionSet.length; optionIndex++) {
						for (var comboIndex = 0; comboIndex < totalCombos.length; comboIndex++) {
							newTotalCombos.push(totalCombos[comboIndex].concat(optionSet[optionIndex]));
						}
					}
					totalCombos = newTotalCombos;
				}
				for (var i = 0; i < totalCombos.length; i++) {
					totalCombos[i] = thisSchemaSet.concat(totalCombos[i]);
				}
				
				callback(totalCombos);
			}
		};
		for (var i = 0; i < orSchemas.length; i++) {
			(function (i) {
				var remaining = [];
				var found = false;
				for (var optionNum = 0; optionNum < orSchemas[i].length; optionNum++) {
					var option = orSchemas[i][optionNum];
					if (thisSchemaSet.indexOf(option, !!callback) == -1) {
						remaining.push(option);
					} else {
						found = true;
					}
				}
				if (remaining.length > 0) {
					var orSelections = [[]];
					for (var remNum = 0; remNum < remaining.length; remNum++) {
						var newCombos = [];
						for (var combNum = 0; combNum < orSelections.length; combNum++) {
							newCombos.push(orSelections[combNum]);
							newCombos.push(orSelections[combNum].concat([remaining[remNum]]));
						}
						orSelections = newCombos;
					} 
					if (!found) {
						orSelections.shift();
					}
					if (callback) {
						orSelectionOptionSets[i] = [];
						for (var j = 0; j < orSelections.length; j++) {
							var orSelectionSet = new SchemaList(orSelections[j]);
							orPending++;
							orSelectionSet.allCombinations(function (subCombos) {
								orSelectionOptionSets[i] = orSelectionOptionSets[i].concat(subCombos);
								gotOrResult();
							});
						}
					} else {
						orSelectionOptionSets[i] = orSelections;
					}
				}
			})(i);
		}
		
		var totalCombos = [new SchemaList([])];
		for (var optionSetIndex = 0; optionSetIndex < orSelectionOptionSets.length; optionSetIndex++) {
			var optionSet = orSelectionOptionSets[optionSetIndex];
			var newTotalCombos = [];
			for (var optionIndex = 0; optionIndex < optionSet.length; optionIndex++) {
				for (var comboIndex = 0; comboIndex < totalCombos.length; comboIndex++) {
					newTotalCombos.push(totalCombos[comboIndex].concat(optionSet[optionIndex]));
				}
			}
			totalCombos = newTotalCombos;
		}
		for (var i = 0; i < totalCombos.length; i++) {
			totalCombos[i] = this.concat(totalCombos[i]);
		}
		
		if (callback) {
			gotOrResult();
		}
		return totalCombos;
	},
	createValue: function(callback, ignoreChoices) {
		if (!ignoreChoices) {
			if (callback != null) {
				this.allCombinations(function (allCombinations) {
					function nextOption(index) {
						if (index >= allCombinations.length) {
							callback(undefined);
						}
						allCombinations[index].createValue(function (value) {
							if (value !== undefined) {
								callback(value);
							} else {
								nextOption(index + 1);
							}
						}, true);
					}
					nextOption(0);
				});
				return;
			}
			// Synchronous version
			var allCombinations = this.allCombinations();
			for (var i = 0; i < allCombinations.length; i++) {
				var value = allCombinations[i].createValue(null, true);
				if (value !== undefined) {
					return value;
				}
			}
			return;
		}

		var basicTypes = this.basicTypes();
		var pending = 0;
		var chosenCandidate = undefined;
		function gotCandidate(candidate) {
			if (candidate !== undefined) {
				var newBasicType = Utils.guessBasicType(candidate);
				if (basicTypes.indexOf(newBasicType) == -1 && (newBasicType != "integer" || basicTypes.indexOf("number") == -1)) {
					candidate = undefined;
				}
			}
			if (candidate !== undefined && chosenCandidate === undefined) {
				chosenCandidate = candidate;
			}
			pending--;
			if (callback && pending <= 0) {
				callback(chosenCandidate);
			}
			if (pending <= 0) {
				return chosenCandidate;
			}
		}

		for (var i = 0; i < this.length; i++) {
			if (this[i].hasDefault()) {
				pending++;
				if (gotCandidate(this[i].defaultValue())) {
					return chosenCandidate;
				}
			}
		}
		
		var enumValues = this.enumValues();
		if (enumValues != undefined) {
			pending += enumValues.length;
			for (var i = 0; i < enumValues.length; i++) {
				if (gotCandidate(enumValues[i])) {
					return chosenCandidate;
				}
			}
		} else {
			pending += basicTypes.length;
			for (var i = 0; i < basicTypes.length; i++) {
				var basicType = basicTypes[i];
				if (basicType == "null") {
					if (gotCandidate(null)) {
						return chosenCandidate;
					}
				} else if (basicType == "boolean") {
					if (gotCandidate(true)) {
						return true;
					}
				} else if (basicType == "integer" || basicType == "number") {
					var candidate = this.createValueNumber();
					if (gotCandidate(candidate)) {
						return chosenCandidate;
					}
				} else if (basicType == "string") {
					var candidate = this.createValueString();
					if (gotCandidate(candidate)) {
						return chosenCandidate;
					}
				} else if (basicType == "array") {
					if (callback) {
						this.createValueArray(function (candidate) {
							gotCandidate(candidate);
						});
					} else {
						var candidate = this.createValueArray();
						if (gotCandidate(candidate)) {
							return chosenCandidate;
						}
					}
				} else if (basicType == "object") {
					if (callback) {
						var candidate = this.createValueObject(function (candidate) {
							gotCandidate(candidate);
						});
					} else {
						var candidate = this.createValueObject();
						if (gotCandidate(candidate)) {
							return chosenCandidate;
						}
					}
				}
			}
		}
		return gotCandidate(chosenCandidate);
	},
	createValueNumber: function () {
		var exclusiveMinimum = this.exclusiveMinimum();
		var minimum = this.minimum();
		var maximum = this.maximum();
		var exclusiveMaximum = this.exclusiveMaximum();
		var interval = this.numberInterval();
		var candidate = undefined;
		if (minimum != undefined && maximum != undefined) {
			if (minimum > maximum || (minimum == maximum && (exclusiveMinimum || exclusiveMaximum))) {
				return;
			}
			if (interval != undefined) {
				candidate = Math.ceil(minimum/interval)*interval;
				if (exclusiveMinimum && candidate == minimum) {
					candidate += interval;
				}
				if (candidate > maximum || (candidate == maximum && exclusiveMaximum)) {
					return;
				}
			} else {
				candidate = (minimum + maximum)*0.5;
			}
		} else if (minimum != undefined) {
			candidate = minimum;
			if (interval != undefined) {
				candidate = Math.ceil(candidate/interval)*interval;
			}
			if (exclusiveMinimum && candidate == minimum) {
				if (interval != undefined) {
					candidate += interval;
				} else {
					candidate++;
				}
			}
		} else if (maximum != undefined) {
			candidate = maximum;
			if (interval != undefined) {
				candidate = Math.floor(candidate/interval)*interval;
			}
			if (exclusiveMaximum && candidate == maximum) {
				if (interval != undefined) {
					candidate -= interval;
				} else {
					candidate--;
				}
			}
		} else {
			candidate = 0;
		}
		return candidate;
	},
	createValueString: function () {
		var candidate = "";
		return candidate;
	},
	createValueArray: function (callback) {
		var thisSchemaSet = this;
		var candidate = [];
		var minItems = this.minItems();
		if (!minItems) {
			if (callback) {
				callback(candidate);
			}
			return candidate;
		}
		var pending = minItems;
		for (var i = 0; i < minItems; i++) {
			(function (i) {
				if (callback) {
					thisSchemaSet.createValueForIndex(i, function (value) {
						candidate[i] = value;
						pending--;
						if (pending == 0) {
							callback(candidate);
						}
					});
				} else {
					candidate[i] = thisSchemaSet.createValueForIndex(i);
				}
			})(i);
		}
		return candidate;
	},
	createValueObject: function (callback) {
		var thisSchemaSet = this;
		var candidate = {};
		var requiredProperties = this.requiredProperties();
		if (requiredProperties.length == 0) {
			if (callback) {
				callback(candidate);
			}
			return candidate;
		}
		var pending = requiredProperties.length;
		for (var i = 0; i < requiredProperties.length; i++) {
			(function (key) {
				if (callback) {
					thisSchemaSet.createValueForProperty(key, function (value) {
						candidate[key] = value;
						pending--;
						if (pending == 0) {
							callback(candidate);
						}
					});
				} else {
					candidate[key] = thisSchemaSet.createValueForProperty(key);
				}
			})(requiredProperties[i]);
		}
		return candidate;
	},
	createValueForIndex: function(index, callback) {
		var indexSchemas = this.indexSchemas(index);
		return indexSchemas.createValue(callback);
	},
	indexSchemas: function(index) {
		var result = new SchemaList();
		for (var i = 0; i < this.length; i++) {
			result = result.concat(this[i].indexSchemas(index));
		}
		return result;
	},
	createValueForProperty: function(key, callback) {
		var propertySchemas = this.propertySchemas(key);
		return propertySchemas.createValue(callback);
	},
	propertySchemas: function(key) {
		var result = new SchemaList();
		for (var i = 0; i < this.length; i++) {
			result = result.concat(this[i].propertySchemas(key));
		}
		return result;
	},
	propertyDependencies: function(key) {
		var result = [];
		var stringDeps = {};
		for (var i = 0; i < this.length; i++) {
			var deps = this[i].propertyDependencies(key);
			for (var j = 0; j < deps.length; j++) {
				if (typeof deps[j] == "string") {
					if (!stringDeps[deps[j]]) {
						stringDeps[deps[j]] = true;
						result.push(deps[j]);
					}
				} else {
					result.push(deps[j]);
				}
			}
		}
		return result;
	},
	isFull: function () {
		for (var i = 0; i < this.length; i++) {
			if (!this[i].isFull()) {
				return false;
			}
			var andSchemas = this[i].andSchemas();
			for (var j = 0; j < andSchemas.length; j++) {
				if (this.indexOf(andSchemas[j], true) == -1) {
					return false;
				}
			}
		}
		return true;
	},
	getFull: function(callback) {
		if (this.length == 0) {
			callback.call(this, this);
			return this;
		}
		var pending = 0;
		var result = [];
		var fixedList = this.fixed();
		function addAll(list) {
			pending += list.length;
			for (var i = 0; i < list.length; i++) {
				list[i].getFull(function(schema) {
					for (var i = 0; i < result.length; i++) {
						if (schema.equals(result[i])) {
							pending--;
							if (pending == 0) {
								var fullList = new SchemaList(result, fixedList);
								callback.call(fullList, fullList);
							}
							return;
						}
					}
					result.push(schema);
					var extendSchemas = schema.extendSchemas();
					addAll(extendSchemas);
					pending--;
					if (pending == 0) {
						var fullList = new SchemaList(result, fixedList);
						callback.call(fullList, fullList);
					}
				});
			}
		}
		addAll(this);
		return this;
	},
	formats: function () {
		var result = [];
		for (var i = 0; i < this.length; i++) {
			var format = this[i].format();
			if (format != null) {
				result.push(format);
			}
		}
		return result;
	},
	xorSchemas: function () {
		var result = [];
		for (var i = 0; i < this.length; i++) {
			result = result.concat(this[i].xorSchemas());
		}
		return result;
	},
	orSchemas: function () {
		var result = [];
		for (var i = 0; i < this.length; i++) {
			result = result.concat(this[i].orSchemas());
		}
		return result;
	}
};
SchemaList.prototype.basicTypes = SchemaList.prototype.types;
SchemaList.prototype.potentialLinks = SchemaList.prototype.links;

publicApi.extendSchemaList = function (obj) {
	for (var key in obj) {
		if (SchemaList.prototype[key] == undefined) {
			SchemaList.prototype[key] = obj[key];
		}
	}
};

publicApi.createSchemaList = function (schemas) {
	if (!Array.isArray(schemas)) {
		schemas = [schemas];
	}
	return new SchemaList(schemas);
};

var SCHEMA_SET_UPDATE_KEY = Utils.getUniqueKey();

function SchemaSet(dataObj) {
	var thisSchemaSet = this;
	this.dataObj = dataObj;

	this.schemas = {};
	this.schemasFixed = {};
	this.links = {};
	this.matches = {};
	this.xorSelectors = {};
	this.orSelectors = {};
	this.dependencySelectors = {};
	this.schemaFlux = 0;
	this.schemasStable = true;

	this.schemasStableListeners = new ListenerSet(dataObj);
	this.pendingNotify = false;

	this.cachedSchemaList = null;
	this.cachedLinkList = null;
}
var counter = 0;
SchemaSet.prototype = {
	update: function (key) {
		this.updateLinksWithKey(key);
		this.updateDependenciesWithKey(key);
		this.updateMatchesWithKey(key);
	},
	updateFromSelfLink: function () {
		this.cachedLinkList = null;
		var activeSelfLinks = [];
		// Disable all "self" links
		for (var schemaKey in this.links) {
			var linkList = this.links[schemaKey];
			for (i = 0; i < linkList.length; i++) {
				var linkInstance = linkList[i];
				if (linkInstance.rel() == "self") {
					linkInstance.active = false;
				}
			}
		}
		// Recalculate all "self" links, keeping them disabled
		for (var schemaKey in this.links) {
			var linkList = this.links[schemaKey];
			for (i = 0; i < linkList.length; i++) {
				var linkInstance = linkList[i];
				if (linkInstance.rel() == "self") {
					linkInstance.update();
					if (linkInstance.active) {
						activeSelfLinks.push(linkInstance);
						linkInstance.active = false;
						// Reset cache again
						this.cachedLinkList = null;
					}
				}
			}
		}
		// Re-enable all self links that should be active
		for (var i = 0; i < activeSelfLinks.length; i++) {
			activeSelfLinks[i].active = true;
		}

		// Update everything except the self links
		for (var schemaKey in this.links) {
			var linkList = this.links[schemaKey];
			for (i = 0; i < linkList.length; i++) {
				var linkInstance = linkList[i];
				if (linkInstance.rel() != "self") {
					linkInstance.update();
				}
			}
		}
		this.dataObj.properties(function (key, child) {
			child.addLink(null);
		});
		this.dataObj.items(function (index, child) {
			child.addLink(null);
		});
	},
	updateLinksWithKey: function (key) {
		var schemaKey, i, linkList, linkInstance;
		var linksToUpdate = [];
		for (schemaKey in this.links) {
			linkList = this.links[schemaKey];
			for (i = 0; i < linkList.length; i++) {
				linkInstance = linkList[i];
				if (linkInstance.usesKey(key) || key == null) {
					linksToUpdate.push(linkInstance);
				}
			}
		}
		if (linksToUpdate.length > 0) {
			var updatedSelfLink = null;
			for (i = 0; i < linksToUpdate.length; i++) {
				linkInstance = linksToUpdate[i];
				var oldHref = linkInstance.active ? linkInstance.rawLink.rawLink.href : null;
				linkInstance.update();
				var newHref = linkInstance.active ? linkInstance.rawLink.rawLink.href : null;
				if (newHref != oldHref && linkInstance.rel() == "self") {
					updatedSelfLink = linkInstance;
					break;
				}
			}
			if (updatedSelfLink != null) {
				this.updateFromSelfLink(updatedSelfLink);
			}
			// TODO: have separate "link" listeners?
			this.invalidateSchemaState();
		}
	},
	updateMatchesWithKey: function (key) {
		// TODO: maintain a list of sorted keys, instead of sorting them each time
		var schemaKeys = [];
		for (schemaKey in this.matches) {
			schemaKeys.push(schemaKey);
		}
		schemaKeys.sort();
		schemaKeys.reverse();
		for (var j = 0; j < schemaKeys.length; j++) {
			var matchList = this.matches[schemaKeys[j]];
			if (matchList != undefined) {
				for (var i = 0; i < matchList.length; i++) {
					matchList[i].dataUpdated(key);
				}
			}
		}
	},
	updateDependenciesWithKey: function (key) {
		// TODO: maintain a list of sorted keys, instead of sorting them each time
		var schemaKeys = [];		
		for (schemaKey in this.dependencySelectors) {
			schemaKeys.push(schemaKey);
		}
		schemaKeys.sort();
		schemaKeys.reverse();
		for (var j = 0; j < schemaKeys.length; j++) {
			var dependencyList = this.dependencySelectors[schemaKeys[j]];
			for (var i = 0; i < dependencyList.length; i++) {
				dependencyList[i].dataUpdated(key);
			}
		}
	},
	alreadyContainsSchema: function (schema, schemaKeyHistory) {
		for (var j = 0; j < schemaKeyHistory.length; j++) {
			var schemaKeyItem = schemaKeyHistory[j];
			if (this.schemas[schemaKeyItem] == undefined) {
				continue;
			}
			for (var i = 0; i < this.schemas[schemaKeyItem].length; i++) {
				var s = this.schemas[schemaKeyItem][i];
				if (schema.equals(s)) {
					return true;
				}
			}
		}
		return false;
	},
	addSchema: function (schema, schemaKey, schemaKeyHistory, fixed) {
		var thisSchemaSet = this;
		if (schemaKey == undefined) {
			schemaKey = Utils.getUniqueKey();
			counter = 0;
		}
		if (fixed == undefined) {
			fixed = true;
		}
		if (schemaKeyHistory == undefined) {
			schemaKeyHistory = [schemaKey];
		} else {
			schemaKeyHistory[schemaKeyHistory.length] = schemaKey;
		}
		if (this.schemas[schemaKey] == undefined) {
			this.schemas[schemaKey] = [];
		}
		this.schemaFlux++;
		if (typeof schema == "string") {
			schema = publicApi.createSchema({"$ref": schema});
		}
		schema.getFull(function (schema, req) {
			if (thisSchemaSet.alreadyContainsSchema(schema, schemaKeyHistory)) {
				thisSchemaSet.schemaFlux--;
				thisSchemaSet.checkForSchemasStable();
				return;
			}
			DelayedCallbacks.increment();

			thisSchemaSet.schemas[schemaKey].push(schema);
			thisSchemaSet.schemasFixed[schemaKey] = thisSchemaSet.schemasFixed[schemaKey] || fixed;

			// TODO: this actually forces us to walk the entire data tree, as far as it is defined by the schemas
			//       Do we really want to do this?  I mean, it's necessary if we ever want to catch the "self" links, but if not then it's not that helpful.
			thisSchemaSet.dataObj.properties(function (key, child) {
				var subSchemaKey = Utils.getKeyVariant(schemaKey, "prop");
				var subSchemas = schema.propertySchemas(key);
				for (var i = 0; i < subSchemas.length; i++) {
					child.addSchema(subSchemas[i], subSchemaKey, schemaKeyHistory);
				}
			});
			thisSchemaSet.dataObj.indices(function (i, child) {
				var subSchemaKey = Utils.getKeyVariant(schemaKey, "idx");
				var subSchemas = schema.indexSchemas(i);
				for (var i = 0; i < subSchemas.length; i++) {
					child.addSchema(subSchemas[i], schemaKey, schemaKeyHistory);
				}
			});

			var ext = schema.extendSchemas();
			for (var i = 0; i < ext.length; i++) {
				thisSchemaSet.addSchema(ext[i], schemaKey, schemaKeyHistory, fixed);
			}

			thisSchemaSet.addLinks(schema.links(), schemaKey, schemaKeyHistory);
			thisSchemaSet.addXorSelectors(schema, schemaKey, schemaKeyHistory);
			thisSchemaSet.addOrSelectors(schema, schemaKey, schemaKeyHistory);
			thisSchemaSet.addDependencySelector(schema, schemaKey, schemaKeyHistory);

			thisSchemaSet.schemaFlux--;
			thisSchemaSet.invalidateSchemaState();
			DelayedCallbacks.decrement();
		});
	},
	addLinks: function (potentialLinks, schemaKey, schemaKeyHistory) {
		var i, linkInstance;
		if (this.links[schemaKey] == undefined) {
			this.links[schemaKey] = [];
		}
		var selfLink = null;
		for (i = 0; i < potentialLinks.length; i++) {
			linkInstance = new LinkInstance(this.dataObj, potentialLinks[i]);
			this.links[schemaKey].push(linkInstance);
			this.addMonitorForLink(linkInstance, schemaKey, schemaKeyHistory);
			linkInstance.update();
			if (linkInstance.active && linkInstance.rawLink.rawLink.rel == "self") {
				selfLink = linkInstance;
			}
		}
		if (selfLink != null) {
			this.updateFromSelfLink(selfLink);
		}
		this.invalidateSchemaState();
	},
	addXorSelectors: function (schema, schemaKey, schemaKeyHistory) {
		var xorSchemas = schema.xorSchemas();
		var selectors = [];
		for (var i = 0; i < xorSchemas.length; i++) {
			var selector = new XorSchemaApplier(xorSchemas[i], Utils.getKeyVariant(schemaKey, "xor" + i), schemaKeyHistory, this);
			selectors.push(selector);
		}
		if (this.xorSelectors[schemaKey] == undefined) {
			this.xorSelectors[schemaKey] = selectors;
		} else {
			this.xorSelectors[schemaKey] = this.xorSelectors[schemaKey].concat(selectors);
		}
	},
	addOrSelectors: function (schema, schemaKey, schemaKeyHistory) {
		var orSchemas = schema.orSchemas();
		var selectors = [];
		for (var i = 0; i < orSchemas.length; i++) {
			var selector = new OrSchemaApplier(orSchemas[i], Utils.getKeyVariant(schemaKey, "or" + i), schemaKeyHistory, this);
			selectors.push(selector);
		}
		if (this.orSelectors[schemaKey] == undefined) {
			this.orSelectors[schemaKey] = selectors;
		} else {
			this.orSelectors[schemaKey] = this.orSelectors[schemaKey].concat(selectors);
		}
	},
	addDependencySelector: function (schema, schemaKey, schemaKeyHistory) {
		var selector = new DependencyApplier(schema, Utils.getKeyVariant(schemaKey, "dep"), schemaKeyHistory, this);
		var selectors = [selector];
		if (this.dependencySelectors[schemaKey] == undefined) {
			this.dependencySelectors[schemaKey] = selectors;
		} else {
			this.dependencySelectors[schemaKey] = this.dependencySelectors[schemaKey].concat(selectors);
		}
	},
	addLink: function (rawLink) {
		if (rawLink == null) {
			this.updateFromSelfLink();
			this.invalidateSchemaState();
			return;
		}
		var schemaKey = Utils.getUniqueKey();
		var linkData = publicApi.create(rawLink);
		var potentialLink = new PotentialLink(linkData);
		this.addLinks([potentialLink], schemaKey);
	},
	addMonitorForLink: function (linkInstance, schemaKey, schemaKeyHistory) {
		var thisSchemaSet = this;
		var rel = linkInstance.rel();
		if (rel === "describedby") {
			var subSchemaKey = Utils.getKeyVariant(schemaKey);
			linkInstance.addMonitor(subSchemaKey, function (active) {
				thisSchemaSet.removeSchema(subSchemaKey);
				if (active) {
					var rawLink = linkInstance.rawLink;
					var schema = publicApi.createSchema({
						"$ref": rawLink.href
					});
					thisSchemaSet.addSchema(schema, subSchemaKey, schemaKeyHistory, false);
				}
			});
		}
	},
	addSchemaMatchMonitor: function (monitorKey, schema, monitor, executeImmediately, impatientCallbacks) {
		var schemaMatch = new SchemaMatch(monitorKey, this.dataObj, schema, impatientCallbacks);
		if (this.matches[monitorKey] == undefined) {
			this.matches[monitorKey] = [];
		}
		this.matches[monitorKey].push(schemaMatch);
		schemaMatch.addMonitor(monitor, executeImmediately);
		return schemaMatch;
	},
	removeSchema: function (schemaKey) {
		//Utils.log(Utils.logLevel.DEBUG, "Actually removing schema:" + schemaKey);
		DelayedCallbacks.increment();

		this.dataObj.indices(function (i, subData) {
			subData.removeSchema(schemaKey);
		});
		this.dataObj.properties(function (i, subData) {
			subData.removeSchema(schemaKey);
		});

		var key, i, j;
		var keysToRemove = [];
		for (key in this.schemas) {
			if (Utils.keyIsVariant(key, schemaKey)) {
				keysToRemove.push(key);
			}
		}
		for (key in this.links) {
			if (Utils.keyIsVariant(key, schemaKey)) {
				keysToRemove.push(key);
			}
		}
		for (key in this.matches) {
			if (Utils.keyIsVariant(key, schemaKey)) {
				keysToRemove.push(key);
			}
		}
		for (i = 0; i < keysToRemove.length; i++) {
			key = keysToRemove[i];
			delete this.schemas[key];
			delete this.links[key];
			delete this.matches[key];
			delete this.xorSelectors[key];
			delete this.orSelectors[key];
			delete this.dependencySelectors[key];
		}

		if (keysToRemove.length > 0) {
			this.invalidateSchemaState();
		}
		DelayedCallbacks.decrement();
	},
	clear: function () {
		this.schemas = {};
		this.links = {};
		this.matches = {};
		this.invalidateSchemaState();
	},
	getSchemas: function () {
		if (this.cachedSchemaList !== null) {
			return this.cachedSchemaList;
		}
		var schemaResult = [];
		var fixedSchemas = {};

		var i, j, key, schemaList, schema, alreadyExists;
		for (key in this.schemas) {
			schemaList = this.schemas[key];
			var fixed = this.schemasFixed[key];
			for (i = 0; i < schemaList.length; i++) {
				schema = schemaList[i];
				if (fixed) {
					fixedSchemas[schema.data.uniqueId] = schema;
				}
				alreadyExists = false;
				for (j = 0; j < schemaResult.length; j++) {
					if (schema.equals(schemaResult[j])) {
						alreadyExists = true;
						break;
					}
				}
				if (!alreadyExists) {
					schemaResult.push(schema);
				}
			}
		}
		var schemaFixedResult = [];
		for (var key in fixedSchemas) {
			schemaFixedResult.push(fixedSchemas[key]);
		}
		this.cachedSchemaList = new SchemaList(schemaResult, schemaFixedResult);
		return this.cachedSchemaList;
	},
	getLinks: function(rel) {
		var key, i, keyInstance, keyList;
		if (this.cachedLinkList !== null) {
			return this.cachedLinkList.rel(rel);
		}
		var linkResult = [];
		for (key in this.links) {
			keyList = this.links[key];
			for (i = 0; i < keyList.length; i++) {
				keyInstance = keyList[i];
				if (keyInstance.active) {
					linkResult.push(keyInstance.rawLink);
				}
			}
		}
		this.cachedLinkList = new LinkList(linkResult);
		return this.cachedLinkList.rel(rel);
	},
	invalidateSchemaState: function () {
		this.cachedSchemaList = null;
		this.cachedLinkList = null;
		this.schemasStable = false;
		this.checkForSchemasStable();
	},
	checkForSchemasStable: function () {
		if (this.schemaFlux > 0) {
			// We're in the middle of adding schemas
			// We don't need to mark it as unstable, because if we're
			//  adding or removing schemas or links it will be explicitly invalidated
			return false;
		}
		var i, key, schemaList, schema;
		for (key in this.schemas) {
			schemaList = this.schemas[key];
			for (i = 0; i < schemaList.length; i++) {
				schema = schemaList[i];
				if (!schema.isComplete()) {
					this.schemasStable = false;
					return false;
				}
			}
		}
		
		var thisSchemaSet = this;
		if (!thisSchemaSet.schemasStable) {
			thisSchemaSet.schemasStable = true;
			notifySchemaChangeListeners(thisSchemaSet.dataObj);
		}
		thisSchemaSet.schemasStableListeners.notify(thisSchemaSet.dataObj, thisSchemaSet.getSchemas());
		return true;
	},
	addSchemasForProperty: function (key, subData) {
		for (var schemaKey in this.schemas) {
			var subSchemaKey = Utils.getKeyVariant(schemaKey, "prop");
			for (var i = 0; i < this.schemas[schemaKey].length; i++) {
				var schema = this.schemas[schemaKey][i];
				var subSchemas = schema.propertySchemas(key);
				for (var j = 0; j < subSchemas.length; j++) {
					subData.addSchema(subSchemas[j], subSchemaKey);
				}
			}
		}
	},
	addSchemasForIndex: function (index, subData) {
		for (var schemaKey in this.schemas) {
			var subSchemaKey = Utils.getKeyVariant(schemaKey, "idx");
			for (var i = 0; i < this.schemas[schemaKey].length; i++) {
				var schema = this.schemas[schemaKey][i];
				var subSchemas = schema.indexSchemas(index);
				for (var j = 0; j < subSchemas.length; j++) {
					subData.addSchema(subSchemas[j], subSchemaKey);
				}
			}
		}
	},
	removeSubSchemas: function (subData) {
		//    throw new Error("This should be using more than this.schemas");
		for (var schemaKey in this.schemas) {
			subData.removeSchema(schemaKey);
		}
	},
	whenSchemasStable: function (handlerFunction) {
		this.schemasStableListeners.add(handlerFunction);
		this.checkForSchemasStable();
	}
};

function LinkInstance(dataObj, potentialLink) {
	this.dataObj = dataObj;
	this.potentialLink = potentialLink;
	this.active = false;
	this.rawLink = null;
	this.updateMonitors = new MonitorSet(dataObj);
}
LinkInstance.prototype = {
	update: function (key) {
		var active = this.potentialLink.canApplyTo(this.dataObj);
		if (active) {
			this.rawLink = this.potentialLink.linkForData(this.dataObj);
		} else {
			this.rawLink = null;
		}
		this.active = active;
		this.updateMonitors.notify(this.active);
	},
	rel: function () {
		return this.potentialLink.rel();
	},
	usesKey: function (key) {
		return this.potentialLink.usesKey(key);
	},
	addMonitor: function (schemaKey, monitor) {
		this.updateMonitors.add(schemaKey, monitor);
	}
};

function XorSchemaApplier(options, schemaKey, schemaKeyHistory, schemaSet) {
	var inferredSchemaKey = Utils.getKeyVariant(schemaKey, "$");
	this.xorSelector = new XorSelector(schemaKey, options, schemaSet.dataObj);
	this.xorSelector.onMatchChange(function (selectedOption) {
		schemaSet.removeSchema(inferredSchemaKey);
		if (selectedOption != null) {
			schemaSet.addSchema(selectedOption, inferredSchemaKey, schemaKeyHistory, false);
		} else if (options.length > 0) {
			schemaSet.addSchema(options[0], inferredSchemaKey, schemaKeyHistory, false);
		}
	});
}

function OrSchemaApplier(options, schemaKey, schemaKeyHistory, schemaSet) {
	var inferredSchemaKeys = [];
	var optionsApplied = [];
	for (var i = 0; i < options.length; i++) {
		inferredSchemaKeys[i] = Utils.getKeyVariant(schemaKey, "$" + i);
		optionsApplied[i] = false;
	}
	this.orSelector = new OrSelector(schemaKey, options, schemaSet.dataObj);
	this.orSelector.onMatchChange(function (selectedOptions) {
		for (var i = 0; i < options.length; i++) {
			var found = false;
			for (var j = 0; j < selectedOptions.length; j++) {
				if (options[i] == selectedOptions[j]) {
					found = true;
					break;
				}
			}
			if (found && !optionsApplied[i]) {
				schemaSet.addSchema(options[i], inferredSchemaKeys[i], schemaKeyHistory, false);
			} else if (!found && optionsApplied[i]) {
				schemaSet.removeSchema(inferredSchemaKeys[i]);
			}
			optionsApplied[i] = found;
		}
		if (selectedOptions.length == 0 && options.length > 0) {
			schemaSet.addSchema(options[0], inferredSchemaKeys[0], schemaKeyHistory, false);
		}
	});
}

function DependencyApplier(schema, schemaKey, schemaKeyHistory, schemaSet) {
	this.inferredSchemaKeys = {};
	this.applied = {};
	this.schema = schema;
	this.schemaKeyHistory = schemaKeyHistory;
	this.schemaSet = schemaSet;

	var keys = this.schema.data.property("dependencies").keys();
	for (var i = 0; i < keys.length; i++) {
		var key = keys[i];
		this.inferredSchemaKeys[key] = Utils.getKeyVariant(schemaKey, "$" + i);
		this.dataUpdated(key);
	}
	return;
}
DependencyApplier.prototype = {
	dataUpdated: function (key) {
		if (key == null) {
			var keys = this.schema.data.property("dependencies").keys();
			for (var i = 0; i < keys.length; i++) {
				var key = keys[i];
				this.dataUpdated(key);
			}
			return;
		}
		if (this.schemaSet.dataObj.property(key).defined()) {
			var depList = this.schema.propertyDependencies(key);
			for (var i = 0; i < depList.length; i++) {
				var dep = depList[i];
				if (typeof dep != "string") {
					this.schemaSet.addSchema(dep, this.inferredSchemaKeys[key], this.schemaKeyHistory, false);
				}
			}
		} else {
			this.schemaSet.removeSchema(this.inferredSchemaKeys[key]);
		}
	}
};

//Tidying
// TODO: check all " == undefined", in case they should be " === undefined" instead (null-safety)
// TODO: profile memory consumption - you're throwing closures around the place, it might go wrong
// TODO: try/catch clauses for all listeners/monitors
// TODO: document everything
// TODO: does the assigned baseUrl/fragment of data change when it's removed or assigned?
// TODO: various things are indexed by keys, and might have multiple entries - if we allow an entry to have more than one key, we need to do fewer calculations, and there is less duplication.  This will also help speed up schema matching, as we won't have any duplicates.

//Features:
// TODO: Speculative schema matching (independent of applied schemas)
// TODO: something about types - list of uniqueIds for the data object defining the type?
// TODO: as long as we keep a request in the cache, keep a map of all custom-defined fragments
// TODO: have monitors return boolean, saying whether they are interested in future updates (undefined means true)
// TODO: re-structure monitor keys
// TODO: separate schema monitors from type monitors?

publicApi.config = {
	antiCacheUrls: false
}
publicApi.UriTemplate = UriTemplate;

})(this); // Global wrapper

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

