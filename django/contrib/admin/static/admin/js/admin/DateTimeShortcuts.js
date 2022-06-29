/*global Calendar, findPosX, findPosY, get_format, gettext, gettext_noop, interpolate, ngettext, quickElement*/
// Inserts shortcut buttons after all of the following:
//     <input type="text" class="vDateField">
//     <input type="text" class="vTimeField">
'use strict';
{
    const DateTimeShortcuts = {
        calendarInputs: [],
        clockInputs: [],
        shortCutsClass: 'datetimeshortcuts', // class of the clock and cal shortcuts
        timezoneWarningClass: 'timezonewarning', // class of the warning for timezone mismatch
        timezoneOffset: 0,
        init: function() {
            const serverOffset = document.body.dataset.adminUtcOffset;
            if (serverOffset) {
                const localOffset = new Date().getTimezoneOffset() * -60;
                DateTimeShortcuts.timezoneOffset = localOffset - serverOffset;
            }

            for (const inp of document.getElementsByTagName('input')) {
                if (inp.type === 'time' && inp.classList.contains('vTimeField')) {
                    DateTimeShortcuts.addNow(inp);
                    DateTimeShortcuts.addTimezoneWarning(inp);
                }
                else if (inp.type === 'date' && inp.classList.contains('vDateField')) {
                    DateTimeShortcuts.addToday(inp);
                    DateTimeShortcuts.addTimezoneWarning(inp);
                }
                else if (inp.type === 'datetime-local' && inp.classList.contains('vDateTimeField')) {
                    DateTimeShortcuts.addNow(inp, '%Y-%m-%dT%H:%M');
                    DateTimeShortcuts.addTimezoneWarning(inp);
                }
            }
        },
        // Return the current time while accounting for the server timezone.
        now: function() {
            const serverOffset = document.body.dataset.adminUtcOffset;
            if (serverOffset) {
                const localNow = new Date();
                const localOffset = localNow.getTimezoneOffset() * -60;
                localNow.setTime(localNow.getTime() + 1000 * (serverOffset - localOffset));
                return localNow;
            } else {
                return new Date();
            }
        },
        // Add a warning when the time zone in the browser and backend do not match.
        addTimezoneWarning: function(inp) {
            const warningClass = DateTimeShortcuts.timezoneWarningClass;
            let timezoneOffset = DateTimeShortcuts.timezoneOffset / 3600;

            // Only warn if there is a time zone mismatch.
            if (!timezoneOffset) {
                return;
            }

            // Check if warning is already there.
            if (inp.parentNode.querySelectorAll('.' + warningClass).length) {
                return;
            }

            let message;
            if (timezoneOffset > 0) {
                message = ngettext(
                    'Note: You are %s hour ahead of server time.',
                    'Note: You are %s hours ahead of server time.',
                    timezoneOffset
                );
            }
            else {
                timezoneOffset *= -1;
                message = ngettext(
                    'Note: You are %s hour behind server time.',
                    'Note: You are %s hours behind server time.',
                    timezoneOffset
                );
            }
            message = interpolate(message, [timezoneOffset]);

            const warning = document.createElement('div');
            warning.classList.add('help', warningClass);
            warning.textContent = message;
            inp.parentNode.appendChild(warning);
        },
        // Add clock widget to a given field
        addNow: function(inp, prefixFormat = '%H:%M') {
            const num = DateTimeShortcuts.clockInputs.length;
            DateTimeShortcuts.clockInputs[num] = inp;

            // Shortcut links (clock icon and "Now" link)
            const shortcuts_span = document.createElement('span');
            shortcuts_span.className = DateTimeShortcuts.shortCutsClass;
            inp.parentNode.insertBefore(shortcuts_span, inp.nextSibling);
            const now_link = document.createElement('a');
            now_link.href = "#";
            now_link.textContent = gettext('Now');
            now_link.addEventListener('click', function(e) {
                e.preventDefault();
                DateTimeShortcuts.handleClockQuicklink(num, -1, prefixFormat);
            });
            shortcuts_span.appendChild(document.createTextNode('\u00A0'));
            shortcuts_span.appendChild(now_link);
        },
        handleClockQuicklink: function(num, val, prefixFormat) {
            let d;
            if (val === -1) {
                d = DateTimeShortcuts.now();
            }
            else {
                d = new Date(1970, 1, 1, val, 0, 0, 0);
            }
            const stepStr = DateTimeShortcuts.clockInputs[num].getAttribute('step') || '60';
            const step = parseInt(stepStr, 10) | 60;
            let timeFormat = prefixFormat;
            // display seconds in timeFormat if step includes seconds
            if (step % 60 !== 0) {
                timeFormat = timeFormat + ':%S';
            }
            DateTimeShortcuts.clockInputs[num].value = d.strftime(timeFormat);
            DateTimeShortcuts.clockInputs[num].focus();
        },
        // Add calendar widget to a given field.
        addToday: function(inp) {
            const num = DateTimeShortcuts.calendarInputs.length;

            DateTimeShortcuts.calendarInputs[num] = inp;

            // Shortcut links (calendar icon and "Today" link)
            const shortcuts_span = document.createElement('span');
            shortcuts_span.className = DateTimeShortcuts.shortCutsClass;
            inp.parentNode.insertBefore(shortcuts_span, inp.nextSibling);
            const today_link = document.createElement('a');
            today_link.href = '#';
            today_link.appendChild(document.createTextNode(gettext('Today')));
            today_link.addEventListener('click', function(e) {
                e.preventDefault();
                DateTimeShortcuts.handleCalendarQuickLink(num, 0);
            });
            shortcuts_span.appendChild(document.createTextNode('\u00A0'));
            shortcuts_span.appendChild(today_link);
        },
        handleCalendarCallback: function(num) {
            const format = get_format('DATE_INPUT_FORMATS')[0];
            return function(y, m, d) {
                DateTimeShortcuts.calendarInputs[num].value = new Date(y, m - 1, d).strftime(format);
                DateTimeShortcuts.calendarInputs[num].focus();
                document.getElementById(DateTimeShortcuts.calendarDivName1 + num).style.display = 'none';
            };
        },
        handleCalendarQuickLink: function(num, offset) {
            const d = DateTimeShortcuts.now();
            d.setDate(d.getDate() + offset);
            DateTimeShortcuts.calendarInputs[num].value = d.strftime('%Y-%m-%d');
            DateTimeShortcuts.calendarInputs[num].focus();
        }
    };

    window.addEventListener('load', DateTimeShortcuts.init);
    window.DateTimeShortcuts = DateTimeShortcuts;
}
