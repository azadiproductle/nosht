import React from 'react'
import { Link } from 'react-router-dom'
import {
  Collapse,
  Navbar as NavbarBootstrap,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink,
} from 'reactstrap'

const SWITCH_MENU_HEIGHT = 400
const BACK_TOP_DEFAULT = 56
let BACK_TOP = BACK_TOP_DEFAULT

const ExtraMenu = ({menu, show_extra}) => {
  if (!menu) {
    return <div/>
  }
  return (
    <div className={'extra-menu fixed-top' + (show_extra ? ' show' : '')}>
      <div className="container">
        {menu.map((item, i) => <span key={i}>{item.name}</span>)}
      </div>
    </div>
  )
}

export default class Navbar extends React.Component {
  constructor (props) {
    super(props)

    this.close = this.close.bind(this)
    this.set_extra = this.set_extra.bind(this)
    this.state = {
      is_open: false,
      show_extra: false,
    }
    let y_pos = window.scrollY
    this.set_extra(y_pos)

    let busy = false
    this.on_desktop = window.innerWidth > 600

    if (this.on_desktop) {
    window.addEventListener('scroll', () => {
      y_pos = window.scrollY
      if (!busy) {
        window.requestAnimationFrame(() => {
          this.set_extra(y_pos)
          // parallax
            BACK_TOP = Math.round(BACK_TOP_DEFAULT + y_pos / 2) + 'px'
            document.getElementById('background-image').style.top = BACK_TOP
          busy = false
        })
        busy = true
      }
    })
  }
  }

  close () {
    this.state.is_open && this.setState({ is_open: false })
  }

  set_extra () {
    if (window.scrollY > SWITCH_MENU_HEIGHT && !this.state.show_extra) {
      this.setState({ show_extra: true })
    }
    if (window.scrollY < SWITCH_MENU_HEIGHT && this.state.show_extra) {
      this.setState({ show_extra: false })
    }
  }

  render () {
    const categories = this.props.company_data ? this.props.company_data.categories : []
    const company = this.props.company_data ? this.props.company_data.company : {}
    const navbar = (
      <NavbarBootstrap key="1" color="light" light fixed="top" expand="md">
        <div className="container">
          <NavbarBrand tag={Link} onClick={this.close} to="/">{company.name}</NavbarBrand>
          <NavbarToggler onClick={() => this.setState({ is_open: !this.state.is_open })} />
          <Collapse isOpen={this.state.is_open} navbar>
            <Nav className="ml-auto" navbar>
              {categories.map((cat, i) => (
                <NavItem key={i} active={cat.slug === this.props.active_page}>
                  <NavLink tag={Link} onClick={this.close} to={`/${cat.slug}/`}>{cat.name}</NavLink>
                </NavItem>
              ))}
            </Nav>
          </Collapse>
        </div>
      </NavbarBootstrap>
    )
    if (!this.on_desktop) {
      return navbar
    } else {
      return [
        navbar,
        <ExtraMenu key="2" menu={this.props.extra_menu} show_extra={this.state.show_extra}/>,
        <div key="3" id="background-image" style={{
          backgroundImage: `url("${this.props.background}/main.jpg")`,
          top: BACK_TOP
        }}/>,
      ]
    }
  }
}
