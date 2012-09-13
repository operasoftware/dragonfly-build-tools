(function()
{
  if (!Element.prototype.matchesSelector)
  {
    Element.prototype.matchesSelector =
      Element.prototype.oMatchesSelector ?
      Element.prototype.oMatchesSelector :
      function(selector)
      {
        var sel = this.parentNode.querySelectorAll(selector);
        for (var i = 0; sel[i] && sel[i] != this; i++);
        return Boolean(sel[i]);
      }
  };

  /* The naming is not precise, it can return the element itself. */
  Element.prototype.get_ancestor = function(selector)
  {
    var ele = this;
    while (ele)
    {
      if (ele.matchesSelector(selector))
        return ele;
      ele = ele.parentElement;
    }
    return null;
  };

  var for_each = Function.prototype.call.bind(Array.prototype.forEach);
  var h1_height = 0;
  var side_panel = null;
  var side_panel_top = -1;

  var set_sidepanel_top = function()
  {
    var scroll_top = document.documentElement.scrollTop || document.body.scrollTop;
    var top = scroll_top > h1_height ? 0 : h1_height - scroll_top;
    if (top != side_panel_top)
    {
      side_panel_top = top;
      side_panel.style.top = top + "px";
    }
  };

  var collapse = function(button)
  {
    button.get_ancestor(".field").classList.add("collapsed");
  };

  var expand = function(button)
  {
    button.get_ancestor(".field").classList.remove("collapsed");
  };

  var click_handler = function(event)
  {
    var target = event.target;
    if (target.classList.contains("expander"))
    {
      var li = target.get_ancestor(".field");
      if (!li) return;

      if (li.classList.contains("collapsed"))
      {
        if (event.shiftKey)
          for_each(li.querySelectorAll(".expander"), expand);
        else
          expand(target);
      }
      else
        for_each(li.querySelectorAll(".expander"), collapse);
    }
    else if (target.classList.contains("default-collapse"))
    {
      window.localStorage.setItem("default-colapse", String(target.checked));
      for_each(document.querySelectorAll(".expander"), target.checked ? collapse : expand);
    }
  };

  window.onload = function()
  {
    var h1 = document.querySelector("h1");
    h1_height = h1 && parseInt(h1.offsetHeight);
    side_panel = document.querySelector(".sidepanel, #logo");
    set_sidepanel_top();
    window.addEventListener("scroll", set_sidepanel_top, false);
    document.addEventListener("click", click_handler, false);
    if (window.localStorage.getItem("default-colapse") == "true" &&
        location.pathname.indexOf("index.html") == -1)
    {
      for_each(document.querySelectorAll(".expander"), collapse);
      document.querySelector(".default-collapse").checked = true;
    }

  };
})();
